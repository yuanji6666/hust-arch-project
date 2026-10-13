# CCAB 四条差异化指令 —— 实现参考

任务：`1714` → `C=1 (SLL)`、`C=7 (SLTIU)`、`A=1 (LB)`、`B=4 (BGEU)`
目标电路：`circuits/cpu21-riscv -单周期24+4ccab指令(me).circ`

---

## 1. 四条指令的完整编码

F 字段全部按**指令字的原始位**取（电路里的输入引脚就是这么接的）：

| 引脚 | 含义 |
|---|---|
| `OP2`…`OP6` | 指令字 bit 2…6（opcode 的低 5 位） |
| `F12` `F13` `F14` | 指令字 bit 12 / 13 / 14（= funct3 的 bit0/1/2） |
| `F25` | 指令字 bit 25（= funct7 的 bit5） |
| `F30` | 指令字 bit 30（= funct7 的 bit0） |

| 指令 | F14 | F13 | F12 | F25 | F30 | OP6 | OP5 | OP4 | OP3 | OP2 | 字面量式 minterm |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SLL`   | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 1 | `~F14·~F13·F12·~F25·~F30·OP6·OP5·~OP4·~OP3·OP2` |
| `SLTIU` | 0 | 1 | 1 | 1 | × | 0 | 0 | 1 | 0 | 1 | `~F14·F13·F12·F25·OP6·OP5·OP4·~OP3·OP2` |
| `BGEU`  | 1 | 1 | 1 | × | × | 1 | 1 | 0 | 0 | 0 | `F14·F13·F12·OP6·OP5·~OP4·~OP3·~OP2` |
| `LB`    | 0 | 0 | 0 | × | × | 0 | 0 | 0 | 0 | 0 | 无（但需带 `OP5=1` 变体，见 §3） |

`×` = 该位不参与译码，不要接进与门。

### 推导依据

```
SLL   : funct7=0000000 funct3=001 opcode=0110011
        OP2..6 = opcode[6:2] = 0110011[6:2] = 01100 → OP6=1 OP5=1 OP4=0 OP3=0 OP2=1 ✓
        F12/F13/F14 = funct3 的位 = 1/0/0     ✓

SLTIU : funct3=011 opcode=0010011
        opcode[6:2] = 0010011[6:2] = 01001 → OP6=0 OP5=0 OP4=1 OP3=0 OP2=1 ✓
        F12/F13/F14 = 1/1/0  → F14=0 F13=1 F12=1  ✓

BGEU  : funct3=111 opcode=1100011
        opcode[6:2] = 1100011[6:2] = 11000 → OP6=1 OP5=1 OP4=0 OP3=0 OP2=0 ✓
        F12/F13/F14 = 1/1/1  ✓
```

---

## 2. 每条指令需要置位/清零的控制信号

`◇控制信号自动生成` 的 16 个输出：`ALU_SRC BEQ BLTU BNE JAL JALR LB MemToReg MemWrite RegWrite S_Type U_Type csr ecall u1 u2`
`◇运算控制器自动生成` 的 4 个输出：`S0 S1 S2 S3`（= ALU_OP）

| 指令 | RegWrite | ALU_SRC | MemToReg | LB | BLTU | ALU_OP | 备注 |
|---|---|---|---|---|---|---|---|
| `SLL`   | **1** | 0 | 0 | 0 | 0 | `0000` | R 型，无立即数 |
| `SLTIU` | **1** | **1** | 0 | 0 | 0 | `1100` | 符号扩展立即数，**无符号**比较 |
| `BGEU`  | 0 | 0 | 0 | 0 | **?** | `1100` | 分支条件，见 §3 |
| `LB`    | 1 | 1 | **1** | **1** | 0 | `0101` | 已实现 |

### ALU_OP 对照（来自 `运算器规格` 表）

```
0000 = X << Y   逻辑左移
0100 = X / Y
0101 = X + Y
1011 = (X < Y) 有符号比较
1100 = (X < Y) 无符号比较     ← SLTIU / BGEU 用这个
```

`SLLI` 已经译到 `ALU_OP=0000`，所以 **`SLL` 的 ALU 侧无需改动**，只要让 RegWrite 多一个 minterm。
`SLTU`（基本 24 条之一）已经用 `1100`，所以 **`SLTIU` 的 ALU 侧也无需改动**。

---

## 3. 关于 `BGEU` 的重要提醒（必读）

`(me).circ` 的控制信号里**没有** `bge`/`bgeu`/`bltu` 分开的比较逻辑 —— 只有 `ALUequal`、`ALUge`、`BLTU` 三个信号。`BLTU` 的实测表达式为：

```
BLTU = F14 & F13 & ? & OP6 & OP5 & ? & ? & ?          （共 8 个字面量）
```

### `F12/F13/F14` 对所有指令都是 funct3 的位

RISC-V 的 bit 14:12 **就是 funct3 位域**；B 型指令把立即数拆到 bit 31/30:25/11:8/7，**刻意避开 14:12**，所以：

- `BLTU` 的 `funct3 = 110` → `F14=1 F13=1 F12=0`
- `BGEU` 的 `funct3 = 111` → `F14=1 F13=1 F12=1`

这与 `BLTU` 实测表达式 `F14 & F13 & ? …` 的前两位吻合（`110` 的前两位都是 1），第三位那个 `?` 应该就是 `~F12`。

> 结论：`BGEU` 的 minterm 与 `BLTU` **只差 `F12`**（`~F12` → `F12`）。

### `BLTU` 与 `BGEU` 的语义差别

- `BLTU`：`rs1 < rs2`（无符号）时跳转 → 用**取反**的比较结果
- `BGEU`：`rs1 >= rs2`（无符号）时跳转 → 用**不取反**的比较结果，即 `BLTU` 条件取反

两者 `ALU_OP` 都是 `1100`（无符号比较）。所以 `BGEU` 有两条实现路线：

1. **新增一个 `BGEU` 控制信号**：把 `BLTU` 那个 minterm 复制一份，`~F12` 换成 `F12`，输出接到 PC 选择逻辑，并在取用 `ALUge`/`ALUequal` 时改用相反极性。
2. **复用 `BLTU` 信号**：分支决策处已经同时拿到比较结果的真/假两个极性，检查是否可直接接出 `BGEU`。

**改之前先用指令探针实测**：把 `BGEU.asm` 汇编成 hex，载入 ROM，单步观察该条指令上 `BEQ`/`BNE`/`BLTU` 各是什么值，据此决定走哪条路线。

---

## 4. 施工步骤（SLL 优先，一次只做一条）

### 第 0 步：备份
```
复制 circuits/cpu21-riscv -单周期24+4ccab指令(me).circ
  → circuits/cpu21-riscv -单周期24+4ccab指令(me).BAK-<日期>.circ
```

### 第 1 步：确认基线能跑（不改任何东西）
1. Logisim 打开 `(me).circ`，左侧选 **`◇单周期RISC-V`**
2. 右键指令存储器（约 `(440,520)`）→ **加载映像** → 选 `riscv-tools/standard-tests/risc-v-理想流水线测试.hex`
3. `Ctrl+K` 开时钟 → 十进制探针（约 `(1500,90)`）应显示 **21**
4. 若不为 21，**先停下**，问题在基线而不在本次改动

### 第 2 步：加 `SLL` 的 RegWrite minterm

`RegWrite` 由或门驱动，实测引脚（来自 `tools/netlist` 的精确输出）：

```
OR Gate  (490,2830)
   out     (490,2830)
   inputs  (460,2780) (460,2790) (460,2800) (460,2810) (460,2820)
           (460,2840) (460,2850) (460,2860) (460,2870) (460,2880)     10 个 minterm
```

需要新增 1 个与门，输入 10 个字面量，输出接到 `RegWrite` 或门**空闲的输入引脚**。该或门已有 10 个输入占满 `2780…2880`（间距 10px，跳过 2830 因为那是它自己的输出行），所以要么把或门加宽，要么把新 minterm 或进已有的 `SLLI` 那条分支。

> **更省事的做法**：找到 `RegWrite` 里对应 `SLLI` 的那个与门，把它复制一份改几个输入 —— `SLL` 与 `SLLI` 只差 `OP6`（`SLLI` 是 0，`SLL` 是 1）。但 `SLLI` 的 `RegWrite` 那条 minterm 里 `OP6` 是取反的，所以要单独拉一根 `OP6` 正相信号。

### 第 3 步：单条验证
1. 用 `riscv-tools/instruction-tests/rars_f0c874c.jar` 把 `riscv-tools/my-4-tests/SLL.asm` 汇编：

```
java -jar rars_f0c874c.jar nc a mc CompactDataAtZero dump .text HexText SLL.hex SLL.asm
```

   注意：`dump .text HexText <file>` 必须是**三个独立参数**，不能加引号包成一段。
   生成的文件**没有** `v2.0 raw` 头，需要手工加上一行。

2. 载入 ROM → `Ctrl+K` → 数码管应按 `SLL.asm` 注释的顺序变化：
   `00000876 → 00008760 → 00087600 → 00876000 → 08760000 → 87600000 → 76000000 → 60000000 → 00000000`

### 第 4 步：`SLTIU`
同样方式：`RegWrite` + `ALU_SRC` + `u1` 各加对应 minterm（`ALU_OP` 不用改）。
验证用 `riscv-tools/my-4-tests/SLTIU.asm`。

### 第 5 步：`BGEU`
**先实测**：把 `BGEU.asm` 汇编成 hex，在 Logisim 里用「指令探针」（`RiscV Probe`，约 `(390,390)`）单步看 `BEQ/BNE/BLTU` 三个信号在 `BGEU` 上分别是什么值，据此决定是复用 `BLTU` 还是新增信号。

---

## 5. 最终验收判据（任务书原文）

| 项目 | 判据 | 出处 |
|---|---|---|
| 单周期 benchmark | 总周期数 **1546**，LED 显示区 **`00000038`** | 任务书 L123 |
| 理想流水线测试 | 总周期数 **21** | 任务书 L198 |
| CCAB 测试程序 | 4 条指令的测试程序接在 `benchmark.asm` **结尾**，benchmark 结束需**等待 Go 按钮**才继续 | 任务书 L127 |

---

## 6. 已知无法自动化的环节

- **指令 ROM 无法从文件外部加载**：程序存在组件运行时状态里，不在 `.circ` 的任何属性中。`logisim.jar` 的 `-tty -load` 载入的是**数据存储器**，对指令存储器无效（已用两个内容完全不同的 hex 验证：trace 完全一致）。
- **组合电路无法无头仿真**：`CircuitState.setValue()` 后 `Propagator.propagate()` 不生效（1024 行真值表只有 1 种输出组合）；`Simulator` 没有 `propagate()` 方法。Logisim 的仿真依赖 GUI 事件循环。
- **结论**：**每条指令的验证都必须由人在 Logisim GUI 里载入 ROM 并观察**。

## 7. 可用工具

`tools/netlist/Netlist.java` —— 用 Logisim 自己的 `getEnds()` 精确导出元件引脚坐标：

```
javac -encoding UTF-8 -cp logisim.jar -d tools/netlist/out tools/netlist/Netlist.java
java -cp "logisim.jar;tools/netlist/out;cs3410.jar;riscv-probe.jar" \
     Netlist "<file.circ>" "<子电路名>" [信号名|@ends|@pins|@literals|@x,y]
```

已知缺陷：表达式解析里非门输入的字面量名解析不出来（输出 `?`），而**引脚坐标是精确的** —— 改线路时以坐标为准。
