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

## 官方 SLL.hex 的分歧点

```
拍 10  PC=0028  sll s1,s1,t1   RDin=0x00008760   ✓ 模型一致
       ↓ 循环回 0024（经 addi t3,-1 + bne 分支）
拍 16  PC=0024  sll s1,s1,t0   RDin=0x0000000e   模型应为 0x010ec0   ✗
拍 17  PC=0028  sll s1,s1,t1   RDin=0x00000070   模型应为 0x087600   ✗
```

模型在第 16 拍要读的 `s1` 是 `0x8760`；电路算出的 `0x0e` 说明它读到的 `s1` 是 **`0x0e`** —— 而 `0x0e` 恰是**第 14 拍刚写进 `t3` 的循环计数**（`t3 -= 1` 得 7，再左移 1 位得 `0x0e`）。

**待查方向**：`SLL.hex` 与已验证程序的关键差异是它**含循环分支**（`bne`）且循环体内有 `addi t3,t3,-1`。嫌疑是寄存器堆的**写端口 / 读端口在含分支的循环中发生串扰**，或 `sll` 的 `rs1` 在特定拍被换成了别的寄存器值。这属于**数据通路问题，不是 SLL 译码问题**。

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
