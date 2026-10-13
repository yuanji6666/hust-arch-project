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
1714  ->  C=1   C=7   A=1   B=4
          │     │     │     └─ B 类（跳转）编号 4
          │     │     └─────── A 类（存储访问）编号 1
          │     └───────────── C 类（运算）编号 7
          └─────────────────── C 类（运算）编号 1
```

### 需新增的 5 条指令

在基本 24 条指令之上新增，最终共 **29 条**：

| 类别 | 编号 | 指令 | 类型 | 功能 | 编码要点 |
|---|---|---|---|---|---|
| C 运算 | 1 | **SLL** | R | 逻辑左移 | `opcode=0110011` `funct3=001` `funct7=0000000` |
| C 运算 | 7 | **SLTIU** | I | 小于立即数置数（无符号） | `opcode=0010011` `funct3=011` |
| A 存储 | 1 | **LB** | I | 加载字节 | `opcode=0000011` `funct3=000` |
| A 存储 | 4 | **LHU** | I | 加载半字 | `opcode=0000011` `funct3=101` |
| B 跳转 | 4 | **BGEU** | B | 无符号大于等于跳转 | `opcode=1100011` `funct3=111` |

全部为标准 RISC-V 编码，**无需自定义指令格式**。

### 实现要点（易错）

- **LB 符号扩展 / LHU 零扩展** —— 这两条同在 A 类，考的正是扩展方向，写反不会报错但结果错。
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

### 我的设计文件（在根目录，直接编辑）

| 文件 | 说明 |
|---|---|
| `cpu21-riscv - 单周期24条指令.circ` | **起点**：单周期 24 条指令 |
| `cpu21-riscv - 单周期28条指令(含SRA_LUI_LB_BLTU).circ` | 单周期 28 条（含 LB，可参考） |
| `cpu21-riscv -单周期24+4ccab指令.circ` | 单周期 + 4 条 CCAB 扩展 |
| `cpu21-riscv -单周期24+4ccab指令(me).circ` | 单周期 + 4 条 CCAB（个人版） |
| `cpu21-riscv - 单周期+单级中断.circ` | 单周期 + 单级中断 |
| `cpu21-riscv - 单周期+多级中断.circ` | 单周期 + 多级嵌套中断 |
| `cpu21-riscv - 理想流水线.circ` | 理想流水线 |
| `cpu21-riscv - 气泡流水线.circ` | 气泡流水线 |
| `cpu21-riscv - 重定向流水线.circ` | 重定向流水线 |
| `cpu21-riscv - 重定向流水线+ccab.circ` | 重定向流水线 + CCAB |
| `cpu21-riscv - 动态分支预测.circ` | 动态分支预测 |
| `cpu21-riscv(answer).circ` | **参考答案电路**（最大，参考用） |

### 资料

| 路径 | 说明 |
|---|---|
| `2026秋硬件综合训练课设资料发布包/` | 任务书、报告模板、RISC-V 手册、指令码表、汇编工具与测试用例 |
| `硬件综合训练课程设计任务书  2026-8-3修订版.docx` | 课程设计任务书 |

### 工具（新增）

| 文件 | 说明 |
|---|---|
| `logisim.jar` | Logisim 2.15.0.2 中文版（自 exe 抽出，构建产物，`.gitignore` 已忽略） |
| `Run-Logisim.cmd` | 启动器（自动定位 Java，支持拖入 `.circ`） |

---

## 四、任务要求与评分

### 主要技术指标

- 支持规定的 32 位 RISC-V 指令集 + 上述 5 条差异化指令
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

1. **先完成单周期 CPU + 5 条差异化指令** —— 第 4 天就要验收，且是流水线的基础
2. 编写覆盖全部 29 条指令的测试程序，在 RARS 上先跑出预期结果，再与 Logisim 比对
3. 逐步推进流水线：理想 → 气泡 → 重定向（目标 75 分线）
4. 加分项按余力选做：中断（+5/+5）、动态分支预测（+10）、FPGA（+5/+5）

### 参考资料

- `2026秋硬件综合训练课设资料发布包/RISC-V指令集手册/` —— 英文规范、中文读本、指令码表
- `2026秋硬件综合训练课设资料发布包/RISC-V汇编工具与测试用例5.0.zip` —— 汇编工具与测试用例
- `2026秋硬件综合训练课设资料发布包/电路框架-cpu21-riscv/` —— 电路框架、`riscv-probe.jar`、`cs3410.jar`
- `cpu21-riscv(answer).circ` —— 参考答案电路
