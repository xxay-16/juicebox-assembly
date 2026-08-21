# juicebox-assembly Cookbook

这份 Cookbook 面向 `juicebox-assembly 0.1.x`，提供可以直接改写使用的 Python 配方。当前版本已经支持读取、校验、统计、规范化写出，以及将指定组件移动到末尾的新分块。

> `.assembly` 保存的是组件排列和方向，不包含核酸序列。修改它不会生成 FASTA，也不需要修改配套的 `.hic` 文件。

## 目录

- [准备环境](#准备环境)
- [安全处理流程](#安全处理流程)
- [读取与解析](#读取与解析)
- [校验与统计](#校验与统计)
- [查询组件和分块](#查询组件和分块)
- [使用 selector](#使用-selector)
- [移动组件](#移动组件)
- [从 ID 文件移动组件](#从-id-文件移动组件)
- [检查编辑结果](#检查编辑结果)
- [写出文件](#写出文件)
- [处理异常](#处理异常)
- [当前版本注意事项](#当前版本注意事项)
- [完整线粒体分块示例](#完整线粒体分块示例)

## 准备环境

项目尚未发布到 PyPI。克隆仓库后使用可编辑模式安装：

~~~bash
python -m pip install -e .
~~~

也可以在源码目录临时设置导入路径：

~~~bash
PYTHONPATH=src python your_script.py
~~~

## 安全处理流程

推荐始终遵循以下顺序：

1. 明确输入文件和输出文件；
2. 读取并校验输入；
3. 在内存中完成编辑；
4. 提交并再次校验；
5. 明确检查目标分块；
6. 写到新的输出文件。

~~~python
from pathlib import Path

from juicebox_assembly import AssemblyFile, Ref, Target

source = Path("genome.review.assembly")
destination = Path("genome.review.edited.assembly")

document = AssemblyFile.load(source)
before = AssemblyFile.validate(document)
before.raise_for_errors()

result = (
    AssemblyFile.edit(document)
    .move_components(
        [Ref.name("ptg000123l")],
        target=Target.last_new_block(),
    )
    .commit()
)

result.validation.raise_for_errors()

AssemblyFile.dump(
    result.document,
    destination,
    overwrite=False,
    atomic=True,
)
~~~

这个流程不会覆盖输入文件。默认情况下，如果输出文件已经存在，`dump()` 会拒绝写入。

## 读取与解析

### 严格读取规范文件

~~~python
from juicebox_assembly import AssemblyFile

document = AssemblyFile.load(
    "genome.review.assembly",
    strict=True,
)
~~~

严格模式要求：

- 文件头为 `>name ID length`；
- 字段之间使用单个空格；
- 文件头 ID 按顺序严格等于 `1..N`；
- 正文不包含空行；
- 正文只包含由单个空格分隔的有符号整数。

### 诊断读取非规范文件

如果旧文件使用制表符、多余空格或不连续 ID：

~~~python
document = AssemblyFile.load(
    "legacy.assembly",
    strict=False,
)
~~~

诊断模式放宽文本格式，但仍会拒绝重复名称、重复 ID、非正长度和未定义正文引用。

诊断文件的源 ID 可能不是 `1..N`。检查结构时可以暂时关闭源编号兼容性：

~~~python
report = AssemblyFile.validate(
    document,
    source_compatibility=False,
)
report.raise_for_errors()
~~~

规范化写出会根据文件头顺序重新生成连续 ID：

~~~python
canonical_text = AssemblyFile.dumps(document)
~~~

### 从字符串读取

~~~python
text = """>a 1 100
>b 2 200
1 -2
"""

document = AssemblyFile.loads(text)
~~~

## 校验与统计

### 查看所有问题

~~~python
report = AssemblyFile.validate(document)

for issue in report.issues:
    print(
        issue.severity.value,
        issue.code,
        issue.message,
        dict(issue.context),
    )
~~~

### 遇到错误立即停止

~~~python
report.raise_for_errors()
~~~

失败时会抛出 `AssemblyValidationError`，异常中保留完整的 `report`。

### 查看统计指标

~~~python
metrics = report.metrics

print("components:", metrics.components)
print("blocks:", metrics.blocks)
print("component uses:", metrics.component_uses)
print("forward:", metrics.forward_components)
print("reverse:", metrics.reverse_components)
print("fragments:", metrics.fragment_records)
print("debris:", metrics.debris_records)
print("total bp:", metrics.total_bp)
print("scaffold N50:", metrics.scaffold_n50_bp)
print("scaffold L50:", metrics.scaffold_l50)
~~~

正文中的每一行称为 block 或 superscaffold。SDK 不会自动把它认定为经过验证的生物学染色体。

## 查询组件和分块

### 按名称查询

~~~python
component = document.component_by_name("ptg000123l")

print(component.key)
print(component.name)
print(component.length)
print(component.source_serial_id)
~~~

组件名称中的数字后缀不一定等于文件头 ID。不要从名称猜测 ID。

### 按源文件 ID 查询

~~~python
component = document.component_by_source_id(123)
~~~

### 按稳定内存 key 查询

~~~python
component = document.component_by_key(document.components[0].key)
~~~

`ComponentKey` 只保证在当前内存文档及其编辑结果中稳定，不应保存为跨文件的永久标识。

### 遍历规范化正文 token

~~~python
serial_by_key = {
    component.key: serial_id
    for serial_id, component in enumerate(document.components, start=1)
}

for block in document.blocks:
    signed_tokens = [
        placement.orientation.sign * serial_by_key[placement.component]
        for placement in block.placements
    ]
    print(block.key.value, signed_tokens)
~~~

### 查找 fragment 和 debris

~~~python
fragments = [
    component
    for component in document.components
    if component.is_fragment
]

debris = [
    component
    for component in document.components
    if component.is_debris
]
~~~

带有 `:::fragment_N` 或 `:::debris` 的组件不会被自动删除。

## 使用 selector

所有编辑操作都使用显式 `Ref`，避免名称、文件 ID 和内存 key 产生歧义：

~~~python
from juicebox_assembly import Ref

by_name = Ref.name("ptg000123l")
by_source_id = Ref.serial_id(123)
by_key = Ref.key(document.components[0].key)
~~~

当前 `0.1.x` 中，`Ref.serial_id()` 指的是解析输入时记录的源文件头 ID。文件经过规范化写出和重新读取后，该 ID 可能改变。跨文件流程优先保存组件名称。

可以在编辑前主动解析 selector：

~~~python
component = Ref.name("ptg000123l").resolve(document)
print(component.length)
~~~

## 移动组件

### 移动一个组件到末尾独立分块

~~~python
from juicebox_assembly import AssemblyFile, Ref, Target

result = (
    AssemblyFile.edit(document)
    .move_components(
        [Ref.name("ptg000123l")],
        target=Target.last_new_block(),
    )
    .commit()
)
~~~

移动操作会：

- 保持文件头组件及长度不变；
- 保持组件原有方向；
- 从源分块移除目标；
- 把目标放入末尾的新分块；
- 在提交时验证组件覆盖和唯一性。

### 按输入顺序移动多个组件

默认的 `order="input"` 保留 selector 输入顺序：

~~~python
result = (
    AssemblyFile.edit(document)
    .move_components(
        [
            Ref.name("ptg000320l"),
            Ref.name("ptg000123l"),
            Ref.name("ptg000145l"),
        ],
        target=Target.last_new_block(),
        order="input",
    )
    .commit()
)
~~~

目标分块顺序为 `ptg000320l, ptg000123l, ptg000145l`，方向仍来自原正文 placement。

### 保留原 assembly 顺序

~~~python
result = (
    AssemblyFile.edit(document)
    .move_components(
        [
            Ref.name("ptg000320l"),
            Ref.name("ptg000123l"),
            Ref.name("ptg000145l"),
        ],
        target=Target.last_new_block(),
        order="assembly",
    )
    .commit()
)
~~~

此时 selector 列表只决定选择集合，目标分块按组件在原 assembly 中出现的顺序排列。

### 理解源分块拆分

如果原分块是：

~~~text
A B C
~~~

移动 `B` 后，结果是三个分块：

~~~text
A
C
B
~~~

不会得到 `A C`，因为这会创建原文件中不存在的 `A-C` 邻接。

### 连续执行多个移动

~~~python
editor = AssemblyFile.edit(document)

editor.move_components(
    [Ref.name("ptg000123l")],
    target=Target.last_new_block(),
)

editor.move_components(
    [Ref.name("ptg000145l")],
    target=Target.last_new_block(),
)

result = editor.commit()
print(len(result.changeset))
~~~

`commit()` 后 editor 会关闭。不要再次对同一个 editor 调用编辑方法或 `commit()`。

## 从 ID 文件移动组件

假设 `mitochondrial_contig.ids` 每行包含一个组件名称：

~~~text
ptg000123l
ptg000145l
ptg000317l
~~~

### 安全读取名称列表

~~~python
from pathlib import Path


def read_unique_names(path: str | Path) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        name = raw_line.strip()
        if not name or name.startswith("#"):
            continue
        if name in seen:
            raise ValueError(
                f"{path}:{line_number}: duplicate component name {name!r}"
            )
        seen.add(name)
        names.append(name)

    if not names:
        raise ValueError(f"{path}: no component names found")
    return names
~~~

### 编辑前检查全部名称

~~~python
from juicebox_assembly import ComponentNotFound


names = read_unique_names("mitochondrial_contig.ids")
missing: list[str] = []

for name in names:
    try:
        document.component_by_name(name)
    except ComponentNotFound:
        missing.append(name)

if missing:
    raise ValueError(f"components not found: {missing}")
~~~

不要在未报告的情况下忽略缺失名称。名称列表只要有一项不存在，就应在写文件前停止。

### 移动并写到新文件

~~~python
from juicebox_assembly import AssemblyFile, Ref, Target


result = (
    AssemblyFile.edit(document)
    .move_components(
        [Ref.name(name) for name in names],
        target=Target.last_new_block(),
        order="input",
    )
    .commit()
)

AssemblyFile.dump(
    result.document,
    "genome.review.mito-last.assembly",
    overwrite=False,
)
~~~

## 检查编辑结果

### 验证末尾分块名称和顺序

~~~python
component_by_key = {
    component.key: component
    for component in result.document.components
}

last_block_names = [
    component_by_key[placement.component].name
    for placement in result.document.blocks[-1].placements
]

if last_block_names != names:
    raise RuntimeError(
        f"unexpected final block: {last_block_names}"
    )
~~~

### 验证方向没有改变

~~~python
orientation_before = {
    placement.component: placement.orientation
    for block in document.blocks
    for placement in block.placements
}

for placement in result.document.blocks[-1].placements:
    if placement.orientation is not orientation_before[placement.component]:
        raise RuntimeError(
            f"orientation changed for {placement.component}"
        )
~~~

### 验证覆盖、唯一性和数量

~~~python
after = result.validation
after.raise_for_errors()

print("components:", after.metrics.components)
print("component uses:", after.metrics.component_uses)
print("blocks before:", len(document.blocks))
print("blocks after:", after.metrics.blocks)
~~~

在默认唯一覆盖规则下，`components` 应等于 `component_uses`。

### 查看变更记录和 ID 映射

~~~python
for change in result.changeset:
    print("components:", [key.value for key in change.component_keys])
    print("source blocks:", [key.value for key in change.source_block_keys])
    print("target block:", change.target_block_key.value)
    print("order:", change.order.value)

print("source ID -> canonical ID:", dict(result.id_map))
~~~

当前 ChangeSet 用于审计移动摘要，尚不能独立执行完整 undo。

## 写出文件

### 默认安全写出

~~~python
output = AssemblyFile.dump(
    result.document,
    "output.assembly",
)
~~~

默认设置：

- `overwrite=False`：拒绝覆盖已有文件；
- `atomic=True`：先写临时文件，再原子替换目标；
- `validate_document=True`：写出前执行结构校验；
- 使用 UTF-8 和 Unix 换行。

### 明确允许覆盖

只有在调用者已经确认目标文件时才使用：

~~~python
AssemblyFile.dump(
    result.document,
    "output.assembly",
    overwrite=True,
)
~~~

### 输出字符串

~~~python
text = AssemblyFile.dumps(result.document)
~~~

### 检查规范化往返

~~~python
rendered = AssemblyFile.dumps(result.document)
reloaded = AssemblyFile.loads(rendered)

assert AssemblyFile.dumps(reloaded) == rendered
~~~

## 处理异常

所有包级异常都继承自 `AssemblyError`，并提供稳定错误码和结构化上下文：

~~~python
from juicebox_assembly import AssemblyError


try:
    document = AssemblyFile.load("input.assembly")
except AssemblyError as exc:
    print("code:", exc.code)
    print("message:", str(exc))
    print("context:", exc.context)
    raise
~~~

常见异常：

| 异常 | 场景 |
| --- | --- |
| `AssemblyParseError` | 文件格式、编码或引用错误 |
| `AssemblyValidationError` | 文档违反结构约束 |
| `ComponentNotFound` | 名称、源 ID 或 key 不存在或有歧义 |
| `AssemblyEditError` | 空选择、重复选择、无效顺序或 editor 已关闭 |
| `AssemblyWriteError` | 输出存在、目录不存在或写入失败 |

处理校验异常时可以查看完整报告：

~~~python
from juicebox_assembly import AssemblyValidationError


try:
    AssemblyFile.validate(document).raise_for_errors()
except AssemblyValidationError as exc:
    for issue in exc.report.errors:
        print(issue.code, issue.message)
~~~

## 当前版本注意事项

- `Ref.serial_id()` 当前表示源文件 ID；规范化并重新读取后可能改变。
- 编辑后 metadata 中的 `source` 和 `source_sha256` 仍表示输入来源，不是编辑后内容摘要。
- `result.validation` 是编辑提交时的结构校验；诊断文件如需检查原始 ID 是否规范，应另行调用 `AssemblyFile.validate(result.document)`。
- `move_components` 会创建末尾新分块，不会合并核酸序列。
- `break_block`、`split_component`、`join_blocks`、block reverse 和 undo 尚未实现。
- 当前项目处于 alpha 阶段，内部模块路径可能变化；优先从 `juicebox_assembly` 顶层导入公共类型。
- 大型真实 `.hic`、`.assembly` 和 ID 文件不应放进 Python wheel。

## 完整线粒体分块示例

~~~python
from pathlib import Path

from juicebox_assembly import (
    AssemblyFile,
    ComponentNotFound,
    Ref,
    Target,
)


source = Path("genome.review.assembly")
id_file = Path("mitochondrial_contig.ids")
destination = Path("genome.review.mito-last.assembly")


def read_unique_names(path: str | Path) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        name = raw_line.strip()
        if not name or name.startswith("#"):
            continue
        if name in seen:
            raise ValueError(
                f"{path}:{line_number}: duplicate component name {name!r}"
            )
        seen.add(name)
        names.append(name)

    if not names:
        raise ValueError(f"{path}: no component names found")
    return names


document = AssemblyFile.load(source)
before = AssemblyFile.validate(document)
before.raise_for_errors()

names = read_unique_names(id_file)

missing: list[str] = []
for name in names:
    try:
        document.component_by_name(name)
    except ComponentNotFound:
        missing.append(name)

if missing:
    raise ValueError(f"components not found: {missing}")

orientation_before = {
    placement.component: placement.orientation
    for block in document.blocks
    for placement in block.placements
}

result = (
    AssemblyFile.edit(document)
    .move_components(
        [Ref.name(name) for name in names],
        target=Target.last_new_block(),
        order="input",
    )
    .commit()
)

result.validation.raise_for_errors()

component_by_key = {
    component.key: component
    for component in result.document.components
}
last_block = result.document.blocks[-1]
last_names = [
    component_by_key[placement.component].name
    for placement in last_block.placements
]

if last_names != names:
    raise RuntimeError("final block order does not match the ID file")

if any(
    placement.orientation is not orientation_before[placement.component]
    for placement in last_block.placements
):
    raise RuntimeError("one or more orientations changed")

AssemblyFile.dump(
    result.document,
    destination,
    overwrite=False,
    atomic=True,
)

print("output:", destination)
print("matched:", len(names))
print("missing:", 0)
print("components:", result.validation.metrics.components)
print("blocks:", result.validation.metrics.blocks)
print("valid:", result.validation.is_valid)
~~~
