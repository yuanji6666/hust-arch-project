# 进度快照（交接文档）

> 目标：在 `circuits/cpu21-riscv -单周期24+4ccab指令(me).circ` 上实现差异化指令
> `SLL`、`SLTIU`、`BGEU`（`LB` 已有），使单周期 CPU 正确执行 24+4=28 条指令；
> 最终通过 benchmark（1546 周期、LED 显示 `00000038`）与理想流水线测试（21 周期）。

---

## 一、当前完成度

| 项 | 状态 | 证据 |
|---|---|---|
| `SLL` 译码 minterm | ✅ **已实现** | 改前 `RegWrite=0` → 改后 `RegWrite=1`，写回值正确 |
| `SLL` 执行正确性 | ✅ **7 个程序验证通过** | 与 ISA 参考模型逐拍零分歧 |
| 官方 `SLL.hex` | ⚠️ 受**既有**循环缺陷影响 | 最小复现 `R1`/`R2` |
| `SLTIU` | ❌ 未实现 | 需扩 `RegWrite` 或门输入 |
| `BGEU` | ❌ 未实现 | `BLTU` 无或门，串接手法不适用 |
| benchmark 1546 周期 | ❌ 未验证 | — |
| 理想流水线 21 周期 | ❌ 未验证 | — |

---

## 二、本轮（第 6 轮）做了什么

### 1. 修好了 `SLTIU` 的前置工具（`tools/netlist/extend_gate.py`）

`RegWrite` 或门现在是 **10 输入**（9 个原有 minterm + SLL 占 1），**已满**。
要给 `SLTIU` 加位置，需扩到 11 输入。但——

**关键发现（本轮取得）**：Logisim 门电路从偶数输入扩到奇数输入会**移动所有已有引脚**。

用 `GateGeom.java` 让 Logisim 自己实例化各级门并报出引脚，得到权威几何：

```
inputs=10  out+0  in-50 -40 -30 -20 -10  +10 +20 +30 +40 +50
inputs=11  out+0  in-50 -40 -30 -20 -10  +0 +10 +20 +30 +40 +50   ← 多一个 in+0
inputs=12  out+0  in-60 -50 -40 -30 -20 -10  +10 +20 +30 +40 +50 +60
```

**规律**：偶数 n → 两侧各 `n/2` 个、跳过 `y+0`；奇数 n → 两侧各 `(n-1)/2` 个、**外加 `y+0` 一个**。AND 与 OR 完全相同。

所以"只加一根线"不可行，必须**同步重连每一根导线**。

### 2. `extend_gate.py` 已修好映射逻辑，但产物仍被 Logisim 拒绝

修正后的映射（贪心分配，保证双射）：

```
old pins: [2780, 2790, 2800, 2810, 2820, 2840, 2850, 2860, 2870, 2880]
new pins: [2780, 2790, 2800, 2810, 2820, 2830, 2840, 2850, 2860, 2870, 2880]
mapping : 2780→2780 2790→2790 2800→2800 2810→2810 2820→2820
          2840→2830 2850→2840 2860→2850 2870→2860 2880→2870
free    : [2880]      ← 空出最下方引脚，正好接 SLTIU 的新 minterm
```

导线改写 5 根，元件数/导线数与原始一致（319 / 1642），XML 用 `ElementTree` 解析完全正常。

**但 Logisim 加载时报 `WireRepair.doOverlaps` 内存爆炸。** 原始文件走同一条流水线正常，
所以问题在扩展产物本身。**尚未定位。**

---

## 三、已定位但**未修**的既有缺陷（会挡住 benchmark）

### 现象

```
轮1（正常）：sll 两次 → 0x10ec → 0x8760
轮2（异常）：循环体**第一条 sll 整个没写回**，s1 仍是 0x8760
             于是第二次 sll 直接 0x8760 << 3 = 0x43b000
```

### 最小复现

`riscv-tools/my-4-tests/repro/R1_slli_init.hex` 与 `R2_addi_init.hex`
（唯一差异是 `s1` 用 `slli` 还是 `addi` 构造）**失败形态完全相同**。

### 已排除的可能

- ❌ **不是** `SLL` 译码的问题 —— 7 个手工程序全部通过
- ❌ **不是**"自写回触发旁路冲突" —— `P_selfwrite`(rd=rs1) 与 `Q_otherreg`(rd=s2) 结果**完全一致**
- ❌ **不是**本次改动引入的 —— 同一程序载入**改前备份**同样读不到正确操作数

### 观察到的形态

循环回跳后的第一条指令，**ALU 的 A 口**读到了**前一条指令写回的寄存器值**，
而不是指令指定的 `rs1`。`MDin`（B 口）显示正确。

### 待查方向

用 `Netlist.java` 解出 `◇单周期RISC-V` 里 **`PC` 多路选择器 → 寄存器堆读地址**
这条通路，重点看分支回跳那一拍的 `rs1` 是否被写回地址覆盖。

---

## 四、可用的工具链（都已实测跑通）

| 工具 | 作用 |
|---|---|
| `tools/netlist/RomLoad.java` | 用反射写 `MemContents`，把测试程序载入 ROM 并另存 `.circ` |
| `tools/netlist/RomDump.java` | 读 ROM 容量与内容 |
| `tools/netlist/Netlist.java` | 用 Logisim `getEnds()` 导出精确引脚坐标（**注意：O(n²)，大电路会 OOM**） |
| `tools/netlist/GateGeom.java` | 让 Logisim 报出各输入数的门引脚几何 |
| `tools/netlist/diff_trace.py` | 用 ISA 参考模型逐拍比对 `-tty table` 的 trace，自动定位首个分歧 |
| `tools/netlist/check_minterms.py` | 逐位验证 minterm 的唯一性与无冲突性 |
| `tools/netlist/add_sll.py` | SLL 的译码改动（已应用） |
| `tools/netlist/extend_gate.py` | 扩或门输入数并重连导线（**映射已修对，产物仍不可加载**） |

### 关键操作要点

**指令 ROM 的内容确实存在 `.circ` 里**（`<a name="contents">` 块，格式
`addr/data: 10 32` + **去前导零**的十六进制，如 `00100493` 存成 `100493`）。

**库弹窗的根因与解法**：`LibraryManager` 先按 `.circ` 目录找
`cs3410.jar`/`riscv-probe.jar`，失败则回退到**进程工作目录**，再失败就**弹文件选择框**。
把工作目录设成 jar 所在处即可彻底避免：

```powershell
Start-Process java -ArgumentList "-jar","logisim.jar","-tty","table","x.circ" `
  -WorkingDirectory "<jar 所在目录>" -RedirectStandardOutput trace.txt
```

---

## 五、下一步（按优先级）

1. **修 `extend_gate.py` 的加载问题** —— 这是 `SLTIU` 的前置条件。
   怀疑点：改写后某引脚上的导线拓扑让 `WireRepair` 退化。可考虑改成
   "删除全部挂在该门上的导线，再按新引脚位置重新生成"，而不是原地改写端点。
2. **加 `SLTIU` 译码**：`RegWrite` 扩 11 输入接新引脚；`ALU_SRC`(9→10)、`u1`(12→13)
   同样处理。每条信号都要 `RegWrite`/`ALU_SRC`/`u1` 三个 minterm。
   `ALU_OP` 不用改（`SLTU` 已用 `1100` 无符号比较）。
3. **实测 `SLTIU.hex`**（用 `RomLoad` + `-tty table` + `diff_trace.py`）。
4. **做 `BGEU`**：`BLTU` 输出**没有或门**（单 minterm 直接由与门驱动），需另想办法。
5. **修循环缺陷** —— 这是 benchmark 的硬门槛，不修则 1546 周期必过不了。

---

## 六、重要提醒

- **正式电路 `circuits/cpu21-riscv -单周期24+4ccab指令(me).circ` 完好**，
  与最后一次提交逐字节一致。备份在 `circuits/*.BAK-20261013-221412.circ`。
- `extend_gate.py` 的旧版本曾产出让 Logisim OOM 的畸形电路，
  **已删除该产物，正式电路从未被它影响**。
- `tools/netlist/out/`、`circuits/*.BAK-*.circ`、`circuits/_*.circ` 均已在 `.gitignore` 中。
