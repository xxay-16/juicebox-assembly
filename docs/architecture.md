# Juicebox Assembly Python SDK 设计

状态：基础解析、校验、规范化写入和首个 `move_components` 编辑闭环已实现；其余操作仍为设计稿。

## 1. 目标

创建一个面向 Juicebox/3D-DNA `.assembly` 文件的 Python 操作库，并提供稳定的 Python SDK。首版聚焦：

- 解析与序列化；
- 结构校验和统计；
- 移动组件或整个分块；
- 截断分块、按碱基坐标切分组件；
- 合并分块；
- 反向、重排等基础操作；
- 原子写入、变更记录和可回滚编辑。

首版不直接编辑二进制 `.hic`，也不在缺少 FASTA 时生成或融合真实核酸序列。

## 2. 核心设计结论

### 2.1 领域对象与文件编号分离

Juicebox 文件头定义 `>name internal_id length`，正文用带符号的编号表示方向。官方导入器用 `abs(id) - 1` 访问头部组件列表，因此兼容输出必须满足：

- 文件头顺序与序列化编号一致；
- 编号连续为 `1..N`；
- 正文编号全部指向对应的头部位置。

SDK 内部不能把这个易变化的序列化编号当成稳定身份。组件在内存中使用独立的 `ComponentKey`，写文件时再由 `IdAllocator` 生成连续编号。

### 2.2 默认不可变、事务式编辑

解析结果 `AssemblyDocument` 为不可变对象。所有操作先进入 `AssemblyEditor`，`commit()` 时统一校验并返回：

```text
EditResult
├── document       新的 AssemblyDocument
├── changeset      可审计的操作记录
├── validation     校验报告
└── id_map         旧编号到新编号的映射
```

在 commit 成功之前不写文件。写入默认采用临时文件加原子替换。

### 2.3 明确区分四类操作

- `break_block`：在组件边界切开正文分块，不改变文件头。
- `split_component`：按 bp 坐标把一个头部组件切成多个 fragment，会改变文件头和编号。
- `join_blocks`：拼接多个正文分块，创建明确的新邻接，不融合核酸实体。
- `fuse_components`：真正合并头部组件和序列；需要 FASTA/坐标映射，首版不实现。

这样可以避免把“切 scaffold”和“切 contig”、把“拼 scaffold”和“合并序列”混为一谈。

## 3. 分层架构

```text
Python SDK / Facade
        │
        ▼
Editor + Operations ─────── ChangeSet / Undo
        │
        ▼
Domain Model ────────────── Selectors / Coordinates
        │
        ├── Validation Rules
        │
        └── Statistics
        │
        ▼
Format Adapter
        ├── Juicebox parser
        └── Juicebox writer + ID canonicalizer
        │
        ▼
Filesystem adapter
        └── atomic write / checksum / backup
```

依赖方向只能向下。领域层不得依赖文件系统、CLI 或第三方数据框架。

## 4. 包结构

推荐发行名 `juicebox-assembly`，Python 导入名 `juicebox_assembly`：

```text
juicebox-assembly/
├── pyproject.toml
├── src/
│   └── juicebox_assembly/
│       ├── __init__.py
│       ├── sdk.py
│       ├── exceptions.py
│       ├── model/
│       │   ├── component.py
│       │   ├── placement.py
│       │   ├── block.py
│       │   ├── document.py
│       │   └── coordinates.py
│       ├── formats/
│       │   └── juicebox/
│       │       ├── parser.py
│       │       ├── writer.py
│       │       └── id_allocator.py
│       ├── operations/
│       │   ├── move.py
│       │   ├── break_block.py
│       │   ├── split_component.py
│       │   ├── join_blocks.py
│       │   └── reverse.py
│       ├── validation/
│       │   ├── rules.py
│       │   └── report.py
│       ├── history/
│       │   ├── changeset.py
│       │   └── editor.py
│       └── cli.py
├── tests/
│   ├── unit/
│   ├── property/
│   ├── integration/
│   └── fixtures/
└── docs/
    ├── format.md
    ├── coordinates.md
    └── api.md
```

核心运行时尽量只用 Python 标准库。开发依赖建议使用 `pytest`、`hypothesis`、`ruff` 和 `mypy`。

## 5. 领域模型

### Component

```python
@dataclass(frozen=True, slots=True)
class Component:
    key: ComponentKey          # SDK 内稳定身份，不写入 assembly
    name: str
    length: int
    source: SourceInterval | None
    tags: frozenset[str]
```

`SourceInterval` 使用 0-based、半开区间 `[start, end)`。对于原始文件中无法可靠恢复来源坐标的 fragment，`source` 可以为空，不能根据名称强行猜测。

### Placement

```python
@dataclass(frozen=True, slots=True)
class Placement:
    component: ComponentKey
    orientation: Orientation   # FORWARD / REVERSE
```

方向属于 placement，不属于 component。同一组件的定义永远保持正向坐标。

### AssemblyBlock

```python
@dataclass(frozen=True, slots=True)
class AssemblyBlock:
    key: BlockKey
    placements: tuple[Placement, ...]
```

每个正文行对应一个 `AssemblyBlock`。名称使用 block 而不是 chromosome，避免把未经验证的分块当成生物学染色体。

### AssemblyDocument

```python
@dataclass(frozen=True, slots=True)
class AssemblyDocument:
    components: ComponentTable
    blocks: tuple[AssemblyBlock, ...]
    metadata: DocumentMetadata
```

`ComponentTable` 同时提供按稳定 key、精确名称和序列化编号查询。对外查询应使用显式 selector，避免字符串和数字产生歧义：

```python
Ref.name("ptg000123l")
Ref.serial_id(123)
Ref.key(component_key)
```

## 6. 操作语义

### 6.1 move

建议提供两个明确入口：

```python
editor.move_components(refs, target=..., order=...)
editor.move_blocks(block_refs, target=...)
```

组件移动规则：

- 默认保留当前方向；
- 默认按 selector 输入顺序组成目标块，也支持 `order="assembly"`；
- 从源块中抽取目标后，剩余内容按连续区间拆分；
- 从 `A B C` 抽取 `B` 后必须得到 `A`、`C`，不能变成 `A C`；
- 插入已有块时，新邻接必须由调用者通过 target 明确表达；
- 移动到末尾独立块使用 `Target.last_new_block()`。

### 6.2 break_block

只允许在 placement 边界切开：

```python
editor.break_block(block, after=Ref.name("A"))
editor.break_block_at(block, placement_index=3)
```

不修改组件定义和长度，也不需要重新解释 bp 坐标。

### 6.3 split_component

坐标默认采用组件自身正向坐标，0-based 半开区间。切点必须满足：

```text
0 < cut < component.length
```

多切点去重、排序后一次完成，避免连续操作造成坐标漂移。

设正向组件为 `A=[0,L)`，在 `p` 切分：

```text
A+  → fragment_1+ fragment_2+
A-  → fragment_2- fragment_1-
```

反向 placement 必须反转 fragment 顺序并同时保持负方向，才能表示原组件完整的反向互补布局。

默认命名策略：

```text
A:::fragment_1
A:::fragment_2
...
```

命名策略作为 `FragmentNamingPolicy` 注入，以便支持已有命名约定和 `:::debris` 标签。所有 fragment 长度之和必须严格等于原组件长度。

若用户给的是 block 全局坐标，必须调用独立接口：

```python
editor.split_at_block_offset(block, offset_bp=...)
```

该接口负责根据 placement 方向换算为组件正向坐标，不能让底层 `split_component` 猜测坐标系。

### 6.4 join_blocks

```python
editor.join_blocks(
    [block_a, block_b, block_c],
    orientations=["+", "-", "+"],
    target=Target.replace_inputs(),
)
```

反转整个 block 时执行：

1. placement 顺序反转；
2. 每个 placement 的方向取反。

`join_blocks` 不创建新的 Component，只改变正文拓扑。组件实体融合单独命名为 `fuse_components`，等 FASTA 适配层存在后再设计。

### 6.5 reverse

分别提供：

- `reverse_component_placement(ref)`：只翻转一个 placement；
- `reverse_block(block)`：反序整个 block 并翻转所有 placement；
- 不提供含义含混的单一 `reverse()`。

## 7. 事务与变更记录

`AssemblyEditor` 维护 staged operations。每个操作生成结构化记录：

```python
@dataclass(frozen=True)
class Change:
    operation: str
    parameters: Mapping[str, object]
    affected_components: tuple[ComponentKey, ...]
    removed_adjacencies: tuple[Adjacency, ...]
    added_adjacencies: tuple[Adjacency, ...]
    warnings: tuple[str, ...]
```

`ChangeSet` 建议包含：

- 输入文件 SHA-256；
- 操作顺序；
- 旧编号到新编号的映射；
- 新增、删除的邻接；
- split 的来源区间；
- 校验结果；
- 输出文件 SHA-256。

首版撤销可以基于不可变 document 快照；后续再为每个操作实现显式 inverse operation。

## 8. 校验体系

校验结果不只返回布尔值：

```python
ValidationReport(
    errors=tuple[Issue, ...],
    warnings=tuple[Issue, ...],
    metrics=AssemblyMetrics(...),
)
```

规则分层：

1. **语法**：头部三列、正整数长度、正文整数 token。
2. **兼容性**：头部编号必须按行严格等于 `1..N`。
3. **引用**：每个正文绝对编号均有定义。
4. **覆盖**：严格模式下每个组件恰好放置一次。
5. **拓扑**：无空块、无意外新邻接、block key 唯一。
6. **长度**：split 前后长度守恒，来源区间连续且不重叠。
7. **操作后条件**：目标集合、方向、顺序和目标位置符合请求。

错误使用稳定代码，例如：

```text
E_PARSE_HEADER
E_ID_NOT_CONTIGUOUS
E_UNDEFINED_REFERENCE
E_DUPLICATE_PLACEMENT
E_SPLIT_OUT_OF_RANGE
E_AMBIGUOUS_SELECTOR
E_UNSUPPORTED_SEQUENCE_FUSION
```

## 9. Python SDK 表面

```python
from juicebox_assembly import AssemblyFile, Ref, Target

document = AssemblyFile.load("genome.review.assembly")
document.validate().raise_for_errors()

editor = document.edit()

editor.move_components(
    [Ref.name("ptg000123l"), Ref.name("ptg000145l")],
    target=Target.last_new_block(),
    order="selection",
)

editor.split_component(
    Ref.name("ptg000008l"),
    cuts=[1_615_905, 1_715_905],
)

editor.join_blocks(
    [Target.block(0), Target.block(1)],
    orientations=["+", "-"],
)

result = editor.commit()
result.document.write(
    "genome.review.edited.assembly",
    id_policy="canonical",
    atomic=True,
)
result.changeset.write_json("genome.review.edited.changes.json")
```

同时保留适合自动化的纯函数层：

```python
result = move_components(document, refs, target)
result = split_component(document, ref, cuts)
result = join_blocks(document, blocks)
```

`sdk.py` 只是便捷门面，核心逻辑全部放在可独立测试的纯操作函数中。

## 10. 异常策略

异常只用于无法继续的调用错误或 I/O 错误；普通校验问题进入 `ValidationReport`。

```text
AssemblyError
├── ParseError
├── SelectorError
│   ├── ComponentNotFound
│   └── AmbiguousComponent
├── OperationError
│   ├── InvalidCut
│   └── InvalidTarget
├── ValidationError
└── SerializationError
```

所有异常包含稳定 `code`、人类可读消息和结构化 `context`。

## 11. 测试策略

必须覆盖：

- 真实文件 parse/write round trip；
- 名称数字后缀与 internal ID 不一致；
- 正向和反向组件 split；
- 多切点 split 的长度守恒；
- 从 `A B C` 移走 `B` 后不产生 `A-C` 邻接；
- block 反转等于“反序并逐个翻转方向”；
- join 后只有明确声明的新邻接；
- 每次操作后的全组件唯一覆盖；
- canonical writer 输出连续 `1..N`；
- 写入失败不破坏原文件。

单元测试使用 `pytest`，组合不变量使用 `hypothesis`。集成测试使用当前项目的脱敏小型 fixture，不把大型 `.hic` 放入测试包。

## 12. 实施阶段

### v0.1：可靠内核

- model、parser、writer；
- strict validator；
- selector；
- `move_components`、`move_blocks`；
- `break_block`、`split_component`；
- `join_blocks`、block reverse；
- 原子写入；
- pytest + property tests；
- 最小公开 SDK。

### v0.2：可审计工作流

- transaction；
- ChangeSet JSON；
- adjacency diff；
- CLI；
- 文档和类型检查。

### v0.3：序列与生态适配

- FASTA 来源区间；
- AGP 导入导出；
- sequence-aware `fuse_components`；
- 3D-DNA 辅助文件兼容性检查。

## 13. 推荐默认值

- Python：3.10+；
- 构建后端：Hatchling；
- 核心运行时：零第三方依赖；
- 模型：frozen dataclass + slots；
- 坐标：0-based、半开区间；
- 编辑：不可变 document + transaction；
- 写出：canonical 连续编号、UTF-8、LF、末尾换行；
- 安全：严格校验、原子写入、默认不覆盖已有输出；
- “合并”的 v1 含义：`join_blocks`，不做序列实体融合。

## 14. 仍需产品层确认的选择

框架已有推荐默认值，但实现前最好确认：

1. SDK 是否只服务 Juicebox `.assembly`，还是未来要把 AGP/GFA 作为同等一等格式；
2. split 是否需要同步生成 FASTA fragment；
3. 是否要求完全复刻 Juicebox 的 fragment/debris 命名；
4. 是否需要 CLI 与 Python SDK 在 v0.1 同时发布；
5. PyPI 发行名最终使用 `juicebox-assembly` 还是项目自定义名称。

## 参考

- [Juicebox AssemblyFileImporter](https://github.com/aidenlab/Juicebox/blob/master/src/juicebox/assembly/AssemblyFileImporter.java)
- [3D-DNA](https://github.com/aidenlab/3d-dna)
