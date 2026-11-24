# 研究初稿与底稿

`research-draft-workpapers` 是一个面向案例、行业、公司和产业链研究的 Codex skill。它把报告写作、资料留证和 Excel 数据复算串联起来，也支持只执行眼下需要的模块，例如只核对来源、更新一张数据表，或增补指定章节。该skill当前建议在obsidian目录中使用。

## 适合用来做什么

| 任务 | 典型交付 |
| --- | --- |
| 研读资料、找证据缺口、讨论框架 | 来源索引、待核实问题、章节安排与证据分配 |
| 建资料底稿 | 带原文定位、原始链接和截图的证据卡 |
| 整理数据或更新图表 | 可复算的 Excel 工作表、图表，以及图源与数据范围说明 |
| 写初稿、局部修订、定稿核对 | 指定正文或检查结果，以及对应的证据与数据入口 |

正文负责论证，资料底稿负责核对原文和出处，数据底稿负责复算。重要事实可沿正文和证据卡回溯到原件与截图，数字与图表另有工作表和单元格范围。模块 M01–M09 的完整说明见 [SKILL.md](SKILL.md)。

## 安装与调用

将完整的 `research-draft-workpapers` 目录克隆或解压到项目的 `.agents/skills/` 下，使入口位于 `.agents/skills/research-draft-workpapers/SKILL.md`。请保留同级的参考文档、脚本和素材目录。打开该项目后，可以在 Codex 对话中输入：

```text
用 $research-draft-workpapers 读这些资料，列出证据缺口，并给一版章节框架。
用 $research-draft-workpapers 给第二节的结论补来源，记录原文位置和截图，只修改该节。
用 $research-draft-workpapers 更新 Excel 底稿和对应图表，并标明数据范围与更新口径。
```

## 仓库内容

- [`SKILL.md`](SKILL.md) 定义模块、交付边界和共用规则。
- [`references/`](references/) 包含项目框架、证据留存、数据、图表和写作修订的细则。
- [`assets/`](assets/) 提供登记模板、Excel 模块说明和可编辑演示工作簿。演示数据为虚构示例。
- [`scripts/`](scripts/) 提供文件与工作簿清点、PDF 截图、交付核对以及 Excel 图表样式辅助函数。参数及适用范围见 [工具与素材说明](references/resource-guide.md)。
- [`tests/`](tests/) 包含 Python 测试和 Excel 演示工作簿的构建脚本。[`agents/openai.yaml`](agents/openai.yaml) 提供 Codex 界面元数据。

## 可选工具与测试

工作流本身可按需使用。清点和交付核对脚本使用 Python 3.10+ 标准库。PDF 截图另需 `pypdf` 和 Poppler 的 `pdftoppm`，裁剪时需要 Pillow。Excel 演示构建脚本需要 Node.js 和已可解析的 `@oai/artifact-tool`。仓库已提供演示工作簿，可以直接打开查看。

在仓库根目录运行下列命令可以检查清点脚本和执行测试。PDF 集成测试还需要 `reportlab` 生成测试用 PDF，并要求 `pdftoppm` 可从 `PATH` 调用。

```sh
python -B scripts/inventory.py --help
python -B -m unittest discover -s tests -v
```
