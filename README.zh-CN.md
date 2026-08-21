# juicebox-assembly

简体中文 | [English](README.md)

`juicebox-assembly` 是一个用于读取、校验和写入 Juicebox/3D-DNA `.assembly` 文件的类型化 Python SDK。

项目目前处于 `v0.1` 基础阶段，已经提供：

- 不可变的领域模型；
- 严格解析和诊断解析；
- 文件结构及 Juicebox 兼容性校验；
- 规范化 UTF-8 序列化；
- 原子文件写入；
- assembly 基础统计指标；
- 将指定组件事务式移动到末尾独立分块。

分块移动、截断、拆分、合并和反向等编辑操作将在此基础上逐步实现。

## 安装

项目尚未发布到 PyPI。克隆仓库后，可以使用可编辑模式安装：

~~~bash
python -m pip install -e .
~~~

要求 Python 3.10 或更高版本，核心运行时仅依赖 Python 标准库。

## 快速开始

~~~python
from juicebox_assembly import AssemblyFile

# 读取 assembly 文件
document = AssemblyFile.load("genome.review.assembly")

# 校验结构并查看统计指标
report = AssemblyFile.validate(document)
report.raise_for_errors()

print(report.metrics.total_bp)
print(report.metrics.scaffold_n50_bp)

# 规范化写出；默认不覆盖已有文件
AssemblyFile.dump(
    document,
    "genome.review.canonical.assembly",
    overwrite=False,
)
~~~

严格模式要求文件使用规范的 Juicebox 空白格式，并且组件 ID 与文件头顺序一致：

~~~python
document = AssemblyFile.load("input.assembly", strict=True)
~~~

诊断模式可以接受一般空白字符和不连续的源 ID。随后通过规范化写出修复格式和编号：

~~~python
document = AssemblyFile.load("input.assembly", strict=False)
canonical_text = AssemblyFile.dumps(document)
~~~

## 移动组件

使用显式 selector，避免混淆组件名称、源文件序列化 ID 和 SDK 内部稳定 key：

~~~python
from juicebox_assembly import Ref, Target

refs = [
    Ref.name("ptg000123l"),
    Ref.serial_id(145),
]

result = (
    AssemblyFile.edit(document)
    .move_components(
        refs,
        target=Target.last_new_block(),
        order="input",
    )
    .commit()
)

print(result.validation.is_valid)
print(dict(result.id_map))

AssemblyFile.dump(
    result.document,
    "genome.review.moved.assembly",
)
~~~

默认的 `order="input"` 保留 selector 输入顺序；使用 `order="assembly"` 可以保留组件在源 assembly 中的顺序。移动时会保留原方向。从分块中间抽取组件后，剩余 placement 会按连续区间拆成多个分块，不会凭空建立新的邻接关系。

## 文件模型

Juicebox `.assembly` 文件由两部分组成：

1. 文件头中的组件定义，格式为 `>名称 ID 长度`；
2. 正文中的分块，每一行使用带符号的组件 ID 表示排列顺序和方向。

SDK 将正文行称为 assembly block 或 superscaffold，不会自动把它们认定为经过验证的生物学染色体。组件的方向属于其正文位置，而不是组件定义本身。

本项目只处理 `.assembly` 的结构信息，不会修改 `.hic` 二进制文件，也不会修改或生成真实核酸序列。

## 项目结构

~~~text
src/juicebox_assembly/
├── model/               不可变领域对象
├── formats/juicebox/    解析器、ID 分配器和规范化写入器
├── validation/          校验规则、统计指标和结构化报告
├── operations/          显式 selector 和纯组件移动操作
├── history/             事务式编辑器和可审计变更记录
├── exceptions.py        稳定的公共异常
└── sdk.py               Python SDK 公共入口
~~~

详细设计参见 [架构文档](docs/architecture.md)，可直接运行的使用配方参见 [Cookbook](docs/cookbook.md)。

## 项目关系

这是一个独立的非官方兼容性项目，与 Aiden Lab、Juicebox 或 3D-DNA 项目不存在隶属或官方认可关系。相关产品和项目名称归各自权利人所有。

## 许可证

本项目使用 [MIT License](LICENSE)。

## 开发与测试

从源码目录运行测试：

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -v
~~~

安装可选的构建依赖后，可以生成源码包和 wheel：

~~~bash
python -m build
~~~

公共 API 统一从 `juicebox_assembly` 顶层导出。项目仍处于 alpha 阶段，内部模块路径暂不承诺兼容性。

## 当前范围

当前版本适合用作 `.assembly` 文件的安全解析、检查、统计、规范化写出，以及将指定组件移动到末尾独立分块。分块移动、截断、拆分、合并和撤销等 API 尚未完成，不建议依赖占位模块构建生产流程。
