# hust-arch-project

华中科技大学《硬件综合训练》课程设计 —— **RISC-V 5 段流水线 CPU（Logisim 平台）**

---

## 一、我的差异化指令任务

| 项目 | 内容 |
|---|---|
| 学号 | U202414862 |
| 班级 | CS2406 |
| 任务编号 | **1714**（对应表头 `C C A B` 四列） |
| 序号 | 198 |

### 编号拆解

```
1714  ->  C=1   C=7   A=1   B=4        （4 位 → 4 条指令）
          │     │     │     └─ B 类（跳转）编号 4
          │     │     └─────── A 类（存储访问）编号 1
          │     └───────────── C 类（运算）编号 7
          └─────────────────── C 类（运算）编号 1
```

> 全班 247 人的 `code` 均为 4 位，解码列也只有 `C1 C2 A B` 四列，故每人都是 4 条差异化指令。

### 需新增的 4 条指令

编号是 **4 位**（`C C A B`），故对应 **4 条**指令。在基本 24 条之上新增，最终共 **28 条**：

| 类别 | 编号 | 指令 | 类型 | 功能 | 编码要点 |
|---|---|---|---|---|---|
| C 运算 | 1 | **SLL** | R | 逻辑左移 | `opcode=0110011` `funct3=001` `funct7=0000000` |
| C 运算 | 7 | **SLTIU** | I | 小于立即数置数（无符号） | `opcode=0010011` `funct3=011` |
| A 存储 | 1 | **LB** | I | 加载字节 | `opcode=0000011` `funct3=000` |
| B 跳转 | 4 | **BGEU** | B | 无符号大于等于跳转 | `opcode=1100011` `funct3=111` |

全部为标准 RISC-V 编码，**无需自定义指令格式**。

> **注意 A 类只取 1 条。** A 类编号 1 是 `LB`；`LHU` 是 A 类编号 **4**，属于别的同学
> （例如 `U202414625` → `code=5743` → A=4 → LHU）。资料包 `CCAB输出汇总.docx` 里列出的
> A 类 6 条（LB/LBU/LH/LHU/SB/SH）是**全班总清单**，不是本人任务，不要照抄。

### 实现要点（易错）

- **LB 符号扩展** —— 字节 bit7 要符号扩展到 32 位。同类的 `LBU` 才是零扩展，别写反。
- **SLTIU**：立即数先**符号扩展**为 32 位，再按**无符号**比较。基本指令集有 `SLT`/`SLTI`/`SLTU`，但**没有** `SLTIU`。
- **BGEU**：按**无符号**比较后跳转。注意与已有的 `BEQ`/`BNE` 以及同类的 `BLT`/`BLTU` 区分。
- **SLL**：R 型，移位量取 `rs2` 低 5 位。基本指令集只有立即数移位 `SLLI`/`SRLI`/`SRAI`，**没有**寄存器移位。

### 基本指令集（24 条，已给定）

`ADD` `ADDI` `AND` `ANDI` `SLLI` `SRAI` `SRLI` `SUB` `OR` `ORI` `XORI` `LW` `SW`
`BEQ` `BNE` `SLT` `SLTI` `SLTU` `JAL` `JALR` `ECALL` `CSRRSI` `CSRRCI` `URET`

> `ECALL` 约定：`$a7==34` 时 LED 输出 `$a0` 的值，否则停机等待 Go 按键。注意显示逻辑需锁存，否则数据一闪而过。

---

## 二、开发环境

### 已配置内容

| 项目 | 说明 |
|---|---|
| Java | Eclipse Temurin JDK 17.0.20.101 |
| 安装路径 | `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot` |
| Git 身份 | `yuanji6666` / `yuanji_hust@qq.com` |
| 远程仓库 | `git@github.com:yuanji6666/hust-arch-project.git`（SSH） |

### 为什么不用资料包里的 logisim exe

资料包中的 `logisim-ita-cn-20200118.exe` 用 **Launch4j** 打包，被配置为使用**捆绑 JRE**，
会强制检查 exe 同级目录下的 JRE 并**无视系统已安装的 Java**，因此启动即报：

```
This application requires a Java Runtime Environment
This application was configured to use a bundled Java Runtime Environment but the runtime is missing or corrupted.
```

该下载包实际并**不包含** JRE 文件夹。解决办法是把 exe 内嵌的真正主程序抽出为 `logisim.jar`
（内嵌 zip 起始偏移 95744，`Main-Class: com.cburch.logisim.Main`，Logisim **2.15.0.2** 中文版），
直接用系统 JDK 17 运行。

### 启动方式

**双击 `Run-Logisim.cmd`**，然后用 `文件 > 打开` 载入 `.circ`；
或者**把 `.circ` 文件拖到 `Run-Logisim.cmd` 上**直接打开。

启动器会自动按以下顺序定位 Java：

1. `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\javaw.exe`
2. `%JAVA_HOME%\bin\javaw.exe`
3. PATH 中的 `javaw`

### SSH 说明

本机 DNS 被代理接管为 fake-IP 模式（`github.com` → `198.18.x.x`），代理**不转发 22 端口**，
因此 `~/.ssh/config` 中已把 GitHub 改走官方备用端点：

```
Host github.com
    HostName ssh.github.com
    Port 443
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
```

另：Git 自带的 MSYS 版 `ssh.exe` 在某些受限环境下会报
`couldn't create signal pipe, Win32 error 5`，故 `~/.gitconfig` 中已指定使用 Windows 自带 OpenSSH：

```ini
[core]
	sshCommand = C:/Windows/System32/OpenSSH/ssh.exe
```

---

## 三、仓库文件说明

### 目录结构

```
hust-arch-project/
├── README.md
├── Run-Logisim.cmd              # 启动器（自动定位 Java，支持拖入 .circ）
├── logisim.jar                  # Logisim 2.15.0.2 中文版（构建产物，已 gitignore）
├── cs3410.jar                   # 第三方库：标准寄存器堆（已 gitignore）
├── riscv-probe.jar              # 第三方库：指令探针 hust2020.Probe2（已 gitignore）
├── circuits/                    # 电路文件（详见下）
├── riscv-tools/                 # RISC-V 测试程序与工具（详见下）
├── docs/                        # 任务解码表、任务书及其文本提取
├── scripts/                     # 辅助脚本
├── tools/                       # 自建工具（netlist 网表提取器）
└── 2026秋硬件综合训练课设资料发布包/   # 课程原始资料包（只读参考，见下）
```

> `logisim.jar` 必须与 `Run-Logisim.cmd` 同级（启动器用 `%~dp0logisim.jar` 定位）。

#### 为什么 `cs3410.jar` / `riscv-probe.jar` 要放在根目录

这两个 jar 是 `.circ` 内 `lib desc="jar#cs3410.jar#…"` 引用的第三方库。Logisim 的 `LibraryManager` 解析顺序是：

1. **先**在 `.circ` 文件自身所在目录找；
2. 找不到就回退到 **Logisim 进程的当前工作目录**；
3. 再找不到就**弹文件选择框**要求手动指定。

启动器把工作目录固定在项目根目录（见 `Run-Logisim.cmd` 里的 `cd /d "%~dp0"`），所以根目录必须有这两个 jar。**否则你打开任何不在 `circuits/` 里的 `.circ`（例如 `2026秋硬件综合训练课设资料发布包/电路框架-cpu21-riscv/cpu21-riscv.circ`、`中断按键信号产生.circ`）都会弹框要库。**

`circuits/` 下也保留了一份副本，用于直接打开该目录内的 `.circ` 时第 1 步就能命中。

### circuits/ —— 电路文件

仅保留 3 个，其余 9 个已删（都是空壳子电路、逐字节重复、或此三者的子集；内容仍在 git 历史的 `init` 提交里）：

| 文件 | 定位 |
|---|---|
| **`circuits/cpu21-riscv -单周期24+4ccab指令(me).circ`** | **唯一的工作文件**。已实现基本 24 条 + `LUI`/`SRA`/`BLTU`/`LB`，并含单级中断(341 元件)与多级中断(385 元件)，内含官方中断测试程序 |
| **`circuits/cpu21-riscv(answer).circ`** | **唯一的完整参考**。12 个文件中只有它有 `数据相关检测逻辑`、`寄存器有效逻辑`、`数据相关检测逻辑-重定向`、`流水线中断`、`动态分支预测`、`BTB表`、`MAX2` |
| **`circuits/cpu21-riscv - 动态分支预测.circ`** | 另一条实现路线（`分支历史表`+`双位预测状态转换`），与 answer 的 `BTB表` 方案可对照 |

**`(me)` 的现状**：4 条差异化指令中只有 `LB` 已实现，缺 **`SLL`、`SLTIU`、`BGEU`**。

> 已删除但可恢复：`单周期24条指令`、`单周期28条指令(含SRA_LUI_LB_BLTU)`（与前者 SHA256 `A1C5AAC4…` 逐字节相同，文件名骗人）、`单周期24+4ccab指令`、`单周期+单级中断`、`单周期+多级中断`、`理想流水线`、`气泡流水线`、`重定向流水线`、`重定向流水线+ccab`。
> 恢复命令：`git checkout init -- "<文件名>"`

### riscv-tools/ —— 测试程序与工具

| 目录 | 内容 |
|---|---|
| `my-4-tests/` | **本人任务的 4 条指令测试程序**：`SLL.asm`、`SLTIU.asm`、`LB.asm`、`BGEU.asm` |
| `standard-tests/` | 标准/流水线测试程序：`risc-v-benchmark_ccab`、`risc-v-理想流水线测试`、`risc-v-移位测试`、`risc-v-走马灯测试`、`risc-v-B指令测试`、`risc-v-JMP测试`、`risc-v-分支相关测试`、`risc-v-分支预测测试`、`risc-v-排序测试` |
| `interrupt-tests/` | 中断测试程序（单级、多级 EPC 内存堆栈 / 硬件堆栈，均 `.asm`+`.hex` 齐全） |
| `instruction-tests/` | 其余单指令测试程序、`CCAB输出汇总.docx`（**逐拍预期输出总表**）、`rars_f0c874c.jar`（汇编器）、`Readme.txt` |

### docs/

| 路径 | 说明 |
|---|---|
| `docs/assignments-decoded.csv` | 全班 247 人的差异化指令解码表（见下） |
| `docs/硬件综合训练课程设计任务书  2026-8-3修订版.docx` | 课程设计任务书（与资料包里的 pdf 同源） |
| `docs/taskbook/taskbook-text.txt` | 任务书正文纯文本（523 行，表格以 `[[TABLE n]]` 占位） |
| `docs/taskbook/tables/` | 任务书的 5 张表格（`table0.csv` ~ `table4.csv`） |

### scripts/

| 脚本 | 用途 |
|---|---|
| `scripts/export-docx.py` | 把 `.docx` 导出为正文文本 + 每张表一个 CSV，便于 grep/diff |

### 课程原始资料包

| 路径 | 说明 |
|---|---|
| `2026秋硬件综合训练课设资料发布包/` | 只读参考，勿改。含任务书 pdf、报告模板、RISC-V 手册与指令码表、电路框架（`cs3410.jar`/`riscv-probe.jar`）、控制器表达式生成表、中断参考电路（`中断按键信号产生.circ`、`中断信号测试模拟电路.circ`）、`正确封装图.png` |

#### 附：docs/assignments-decoded.csv

从资料包中 `2026秋《硬件综合训练》差异化指令任务分配.pdf` 提取并解码，便于核对本人任务、
以及团队分工时查看同学抽到的指令。列含义：

| 列 | 说明 |
|---|---|
| `student_id` | 学号 |
| `code` | 4 位任务编号，对应 pdf 表头的 `C C A B` 四列 |
| `C1` `C2` | C 类（运算）编号，十六进制，含 `A` |
| `A` | A 类（存储访问）编号 |
| `B` | B 类（跳转）编号 |
| `classNo` | 班级内序号 |
| `C1_instr` `C2_instr` `A_instr` `B_instr` | 解码后的指令名 |

> 注：pdf 中部分学号在表格中位数不足（原文如此），故本表收录 247 条而非全部学生。
> 本人记录已逐字符核对：`U202414862` → `code=1714` → `C=1,7 A=1 B=4`。

### 工具（新增）

| 文件 | 说明 |
|---|---|
| `logisim.jar` | Logisim 2.15.0.2 中文版（自 exe 抽出，构建产物，`.gitignore` 已忽略） |
| `Run-Logisim.cmd` | 启动器（自动定位 Java，支持拖入 `.circ`） |

---

## 四、任务要求与评分

### 主要技术指标

- 支持规定的 32 位 RISC-V 指令集 + 上述 4 条差异化指令
- 支持**多级嵌套中断**，利用中断触发扩展指令集测试程序
- 支持 **5 段流水机制**，可处理数据冒险、结构冒险、分支冒险
- 能运行自己设计的测试程序，**覆盖所有指令**
- 能运行教师提供的标准测试程序，并**自动统计执行周期数**
- 能自动统计：无条件分支指令数、条件分支成功次数、插入气泡数、load-use 冲突次数；
  动态分支预测流水线需统计预测成功/失败次数

### 评分标准（过程与结果，占 70%）

| 完成度 | 分数 |
|---|---|
| 单周期 CPU 设计与实现 | 50 |
| 理想流水线的多周期 CPU | 55 |
| 气泡流水线 | 65 |
| **重定向流水线** | **75** |
| 实现单级中断 | +5 |
| 实现多级嵌套中断 | +5 |
| 完成流水中断机制 | +5 |
| 完成动态预测方式的分支冒险处理 | +10 |
| 实现单周期上开发板（FPGA） | +5 |
| 实现流水线上开发板（FPGA） | +5 |

其余：团队作业 10%，报告和图纸 20%。成绩分不及格/及格/中/良好/优秀五级。

### 时间安排（共 2 周）

| 时间 | 事项 |
|---|---|
| 第 1 天 | 实验室布置任务、集中讲解、领取设备 |
| 第 1~3 天 | 查阅资料，方案设计 |
| **第 4 天** | **中期进度检查：单周期 CPU 验收 + 文档检查** |
| 第 6~10 天 | 阶段性成果随时检查 |
| **第 10 天** | **最终结果验收** |
| 10~30 天 | 团队任务 |

### 提交要求

- 报告使用《硬件综合训练》课程设计报告**模板**，A4 双面打印
- **报告总页数不超过 40 页**
- 阶段性成果能在**头歌**上完成检查的必须留下记录
- 最终版本找指导教师检查，检查后在**纸质检查表**上留记录
- 报告提交：[腾讯文档表单](https://docs.qq.com/form/page/DYmVrV1ZtZUFSR2xR)

> **验收采用答辩方式，抄袭与被抄袭均按零分处理。**

---

## 五、建议的开发顺序

1. **先完成单周期 CPU + 4 条差异化指令** —— 第 4 天就要验收，且是流水线的基础
2. 编写覆盖全部 28 条指令的测试程序，在 RARS 上先跑出预期结果，再与 Logisim 比对
3. 逐步推进流水线：理想 → 气泡 → 重定向（目标 75 分线）
4. 加分项按余力选做：中断（+5/+5）、动态分支预测（+10）、FPGA（+5/+5）

### 参考资料

- `2026秋硬件综合训练课设资料发布包/RISC-V指令集手册/` —— 英文规范、中文读本、指令码表
- `2026秋硬件综合训练课设资料发布包/RISC-V汇编工具与测试用例5.0.zip` —— 汇编工具与测试用例（已解压到 `riscv-tools/`）
- `2026秋硬件综合训练课设资料发布包/电路框架-cpu21-riscv/` —— 电路框架、`riscv-probe.jar`、`cs3410.jar`
- `circuits/cpu21-riscv(answer).circ` —— 参考答案电路
- `docs/taskbook/taskbook-text.txt` —— 任务书全文纯文本（便于检索）

### 验证材料（容易被忽略，但是验收依据）

资料包里有针对**本人这 4 条指令**的现成测试程序和预期输出，已解压并归类到 `riscv-tools/`：

| 用途 | 文件 |
|---|---|
| SLL 测试 | `riscv-tools/my-4-tests/SLL.asm` |
| SLTIU 测试 | `riscv-tools/my-4-tests/SLTIU.asm` |
| LB 测试 | `riscv-tools/my-4-tests/LB.asm` |
| BGEU 测试 | `riscv-tools/my-4-tests/BGEU.asm` |
| **逐拍预期输出总表** | `riscv-tools/instruction-tests/CCAB输出汇总.docx` |
| 汇编器 | `riscv-tools/instruction-tests/rars_f0c874c.jar` |
| 控制信号表达式生成表 | `2026秋硬件综合训练课设资料发布包/电路框架-cpu21-riscv/RISC-V单周期硬布线控制器表达式自动生成（2022-8-19）.xlsx` |

### 施工文档

**`docs/ccab-encoding.md`** —— 4 条差异化指令的逐位编码、需要置位的控制信号、`SLL` 的施工步骤（含从电路实测出的或门引脚坐标）、`BGEU` 的陷阱说明、以及验收判据。

> 该文档记录了**当前无法自动化的环节**：指令 ROM 只能由人在 Logisim GUI 里手动载入，组合电路也无法无头仿真。因此每条指令改完都必须人工载入 ROM 观察数码管与周期数。

关于测试程序的两点要点：

- `.asm` 需用 RARS 汇编成 `.hex` 才能载入 Logisim 的指令 ROM。按 `riscv-tools/instruction-tests/Readme.txt`
  要求：输出格式以 `v2.0 raw` 开头，内存配置选**紧凑（compact）**模式。
- 每个 `.circ` 里有 **6 个指令 ROM**（分别属于 `单周期RISC-V` / `理想流水线` / `气泡流水线` /
  `重定向流水线` / `单周期+单级中断` / `单周期+多级中断` 子电路），规格均为 1024 字 × 32 位。
  测试时把 `.hex` 载入**对应子电路**的那个 ROM。

> ⚠️ 程序能载入 ≠ 能跑通。若 CPU 未实现某条指令，载入含该指令的程序会导致译码错误、输出全错。
> 这正是当前状态：4 条差异化指令中 `SLL`/`SLTIU`/`BGEU` 未实现，故这些测试程序暂时跑不出预期输出。
