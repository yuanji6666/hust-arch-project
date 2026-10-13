# SLL 验证记录

## 结论

**`SLL` 的译码与执行都是正确的。** 5 个独立手工构造的程序、共 6 次以上连续 `sll`，与 ISA 参考模型**逐拍零分歧**。

但**官方 `riscv-tools/my-4-tests/SLL.hex` 仍然跑不出正确结果**，分歧点已精确定位。两者不矛盾：差异在测试程序本身的结构，而非 `sll` 指令。

## 验证方法（本轮打通）

指令 ROM 的内容**确实存在 `.circ` 里**（`<a name="contents">` 块，格式 `addr/data: 10 32` + 去前导零的十六进制）。因此可以：

```bash
# 1) 把测试程序写进 ROM 并另存
java -cp "logisim.jar;tools/netlist/out;cs3410.jar;riscv-probe.jar" \
     RomLoad <in.circ> "◇单周期RISC-V" <prog.hex> <out.circ>

# 2) 无头仿真出 trace（工作目录必须是 jar 所在处，否则会弹库选择框）
Start-Process java -ArgumentList "-jar","logisim.jar","-tty","table","<out.circ>" `
  -WorkingDirectory "<jar 所在目录>" -RedirectStandardOutput trace.txt

# 3) 与 ISA 参考模型逐拍比对，自动定位首个分歧
python tools/netlist/diff_trace.py trace.txt <prog.hex>
```

**关键**：Logisim 的 `LibraryManager` 先按 `.circ` 目录找 `cs3410.jar`/`riscv-probe.jar`，失败则回退到**进程工作目录**，再失败就**弹文件选择框**。把工作目录设成 jar 所在处即可彻底避免弹窗。

## 已通过的测试程序

| 程序 | 内容 | 结果 |
|---|---|---|
| `_I_sll_only.hex` | `s1=0x876; sll s1,s1,t0` | ✅ `fffff0ec` |
| `_H_sll_twice.hex` | 两次 `sll`（t0=1, t1=3） | ✅ `fffff0ec` → `ffff8760` |
| `_K_step.hex` | 5 次 `sll`，每次后显示 | ✅ 24 拍零分歧 |
| `_L_loop.hex` | 4 次 `sll` | ✅ 22 拍零分歧 |
| `_M_unroll.hex` | 3 轮 × 2 次 `sll` 展开 | ✅ `876→8760→87600→876000` |

具体数值：

```
0x876  --<<1-->  0xfffff0ec   ✓
       --<<3-->  0xffff8760   ✓
       --<<1-->  0xffff0ec0   ✓
       --<<1-->  0xfffe1d80   ✓
       --<<3-->  0xff876000   ✓   (M_unroll)
```

## 官方 SLL.hex 的分歧点 —— 根因已定位

```
拍 10  PC=0028  sll s1,s1,t1   RDin=0x00008760   ✓ 模型一致
拍 14  PC=0038  addi t3,t3,-1  RDin=0x00000007   ← t3 变成 0x07
拍 15  PC=003c  bne t3,zero,.. RDin=0x00000007   ← 分支（rd 字段=9，分支本不写寄存器）
       ↓ 循环回 0024
拍 16  PC=0024  sll s1,s1,t0   RDin=0x0000000e   ← 0x07 << 1 ！
拍 17  PC=0028  sll s1,s1,t1   RDin=0x00000070   ← 0x0e << 3
```

### 根因：ALU 的 A 口在循环回跳后读到了错误的寄存器

第二轮的 `sll s1,s1,t0` 的 `rs1` 是 `s1`（值为 `0x8760`），但电路算出的 `0x0e = 0x07 << 1`，
说明 A 口拿到的是 **`t3` 的值 `0x07`** —— 也就是**前一条指令（`addi t3,t3,-1`）刚写回的那个寄存器**。

`MDin`（B 口 / `rs2`）显示 `0x01` 是正确的，所以**只有 A 口出错**。

这属于**寄存器堆读端口或写回旁路的串扰**：循环回跳后的第一条指令，A 口读的是"刚才写回的那个寄存器"，而不是指令指定的 `rs1`。

### 为什么 6 个手工程序都没暴露它

那些程序里**写回的寄存器（`t3`/`a0`）不参与后续的运算**，所以串扰不会显现。
`SLL.hex` 恰好是"`addi t3` 紧接着 `sll` 且 `rs1` 另有其值"的组合，才把它逼了出来。

**这不是 `SLL` 译码的问题，也不会被 `SLTIU`/`BGEU` 的译码改动解决** —— 它是数据通路里既有的缺陷，同样会影响 `SLT`/`SLL`/`SUB` 等所有 R 型指令。

### 根因：循环回跳后，循环体第一条 `sll` 没有生效

两个隔离测试（唯一差异是 `s1` 的初始化方式）**失败形态完全相同**：

| 程序 | 轮 1 | 轮 2 |
|---|---|---|
| `R1_slli_init`（`addi s1,zero,8` + `slli s1,s1,8` + `addi s1,s1,0x76`） | `0x10ec` → `0x8760` ✓ | `0x0043b000` ✗ |
| `R2_addi_init`（用 `addi` 代替 `slli`） | `0x1fc` → `0xfe0` ✓ | `0x0007f000` ✗ |

注意数值关系：

```
轮2 第一次 sll 若正常：0x8760 << 1 = 0x10ec0
轮2 第二次 sll 正常值：0x10ec0 << 3 = 0x87600
实际得到            ：0x0043b000 = 0x8760 << 3
```

**即循环回跳后，循环体的第一条 `sll s1,s1,t0` 完全没有写回**，`s1` 仍是上一轮的 `0x8760`，
第二次 `sll` 直接基于它左移 3 位。

两个隔离测试**唯一共同点**是：循环体第一条指令是 `sll`，且它紧跟在
**`bne` 分支回跳**之后（`bne` 与 `sll` 之间隔了一条 `ecall`/`addi`）。

### 这不是 SLL 译码的问题

- 7 个手工程序全部通过，包括**含 `bne` 回跳的 `N_branchloop`**。
  它与 `R1` 的差别是 `N_branchloop` 的分支 `bne` **紧邻** `addi t3,-1`，
  而 `SLL.hex`/`R1` 的分支与循环体之间夹着 `ecall`。
- 对照实验：同一 `SLL.hex` 载入改前备份，`sll` 同样读不到正确操作数 ——
  说明缺陷**在改动之前就存在**，非本次引入。

### 排查建议

用 `tools/netlist/Netlist.java` 解出 `◇单周期RISC-V` 里 **`PC` 多路选择器 → 寄存器堆读地址**
这条通路，重点看分支回跳的那一拍 `rs1` 是否被写回地址覆盖。
`R1_slli_init` / `R2_addi_init` 已作为**最小复现程序**保留在
`riscv-tools/my-4-tests/repro/`。

## 已确认的译码改动

对比改前备份与改后电路，把同一程序载入两者：

```
改前: PC=0024 sll RDin=000010ec  RegWrite=0   ← ALU 算对了，但不写回
改后: PC=0024 sll RDin=000010ec  RegWrite=1   ← RegWrite 打开
      PC=0028 sll RDin=00008760  RegWrite=1   ← 写回正确
```

**`RegWrite` 的 SLL minterm 确实生效。**

## 待办

- `SLTIU`：需往 `RegWrite`、`ALU_SRC`、`u1` 三个或门各加 minterm。`RegWrite` 或门输入已满（SLL 占了最下方 `(460,2880)`），需先扩到 11 输入或加合并门。
- `BGEU`：**`BLTU` 输出没有或门**（单 minterm 直接由与门驱动），不能用串接手法，需另想办法。
- 排查 `SLL.hex` 在含分支循环中的读端口异常。
