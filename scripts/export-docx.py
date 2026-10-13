"""把 .docx 导出为「正文纯文本 + 每张表一个 CSV」，便于 grep 与 diff。

用法（在仓库根目录执行）：
    python scripts/export-docx.py docs/硬件综合训练课程设计任务书  2026-8-3修订版.docx docs/taskbook

输出：
    <out>/taskbook-text.txt   正文，表格位置以 [[TABLE n]] 占位，顺序与文档一致
    <out>/tables/table{n}.csv 每张表格一个 CSV
"""

import csv
import os
import sys

import docx
from docx.oxml.ns import qn


def main(src: str, out: str) -> None:
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    d = docx.Document(src)

    lines: list[str] = []
    table_index = 0
    # 按文档真实顺序遍历：段落与表格交错
    for child in d.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = "".join(n.text or "" for n in child.iter(qn("w:t")))
            if text.strip():
                lines.append(text.strip())
        elif child.tag == qn("w:tbl"):
            lines.append(f"[[TABLE {table_index}]]")
            table_index += 1

    text_path = os.path.join(out, "taskbook-text.txt")
    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"正文段落 {len(lines)} 行 -> {text_path}")
    for i, t in enumerate(d.tables):
        path = os.path.join(out, "tables", f"table{i}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for row in t.rows:
                w.writerow([c.text.strip().replace("\n", " ") for c in row.cells])
        print(f"  表格{i}: {len(t.rows)} 行 x {len(t.columns)} 列 -> {path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
