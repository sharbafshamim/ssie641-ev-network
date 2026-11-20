#!/usr/bin/env bash
# Build paper/report.pdf and paper/report.docx from paper/report.md.
# Needs pandoc, wkhtmltopdf and Python with matplotlib.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
f1 = r"$\mathrm{coverage}(\varepsilon)=\frac{1}{n(n-1)}\sum_{a\neq b}\mathbf{1}\left[A(a)\cap A(b)\neq\emptyset\right]$"
f2 = r"$\mathrm{weighted:}\ \ \frac{\sum_{a\neq b}P_aP_b\,\mathbf{1}\left[A(a)\cap A(b)\neq\emptyset\right]}{\sum_{a\neq b}P_aP_b}$"
fig = plt.figure(figsize=(7, 1.2)); fig.text(0.02, 0.62, f1, fontsize=13); fig.text(0.02, 0.12, f2, fontsize=13)
fig.savefig("paper/formula.png", dpi=200, bbox_inches="tight")
PY
pandoc -f markdown-implicit_figures paper/report.md -s --metadata pagetitle="Coverage Is Not Connectivity" \
  -c "$PWD/paper/style.css" -o /tmp/report.html
python3 - <<'PY'
import re, os
h = open("/tmp/report.html").read()
h = h.replace("../results/figures/", os.getcwd() + "/results/figures/")
h = re.sub(r'<div class="sourceCode"[^>]*><pre[^>]*class="sourceCode latex">.*?</pre></div>',
           f'<p><img src="{os.getcwd()}/paper/formula.png" style="width:70%"></p>', h, flags=re.S)
open("/tmp/report.html", "w").write(h)
PY
wkhtmltopdf -q --enable-local-file-access --page-size Letter -B 18mm -T 18mm -L 16mm -R 16mm /tmp/report.html paper/report.pdf
echo "wrote paper/report.pdf"
# Word version: the same markdown, with the formula block replaced by its image
python3 - <<'PY2'
import re
s = open("paper/report.md").read()
s = re.sub(r"```latex\n.*?\n```", "![](formula.png){width=70%}", s, flags=re.S)
open("/tmp/report_docx.md", "w").write(s)
PY2
REF=()
[ -f paper/reference.docx ] && REF=(--reference-doc paper/reference.docx)
pandoc -f markdown-implicit_figures /tmp/report_docx.md "${REF[@]}" --resource-path paper:results/figures \
  -o paper/report.docx
echo "wrote paper/report.docx"
