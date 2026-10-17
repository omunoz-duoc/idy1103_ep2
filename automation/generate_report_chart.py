#!/usr/bin/env python3
"""Generate the report's A/C latency chart from the completed suite CSV."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    root = Path(__file__).resolve().parent.parent
    with (root / 'evidencias/comparacion_carga.csv').open(encoding='utf-8') as handle:
        records = {(row['case'], row['stage']): float(row['median_ms']) for row in csv.DictReader(handle)}
    labels = ['Q1 · Operación', 'Q2 · Tesorería', 'Q3 · Compras', 'Q4 · CRM', 'Q5 · Gerencia']
    cases = [f'Q{n}' for n in range(1, 6)]
    figure, axis = plt.subplots(figsize=(9, 3.8))
    for stage, offset, color, label in [('A', -0.19, '#64748b', 'Antes · A'),
                                        ('C', 0.19, '#0f766e', 'Optimizada + índice · C')]:
        bars = axis.bar([n + offset for n in range(5)], [records[(case, stage)] for case in cases],
                        width=0.36, color=color, label=label)
        axis.bar_label(bars, labels=[f'{records[(case, stage)]:.2f}'.replace('.', ',') for case in cases],
                       padding=4, fontsize=9)
    axis.set_xticks(range(5), labels)
    axis.set_ylabel('Mediana del tiempo del cliente (ms)')
    axis.set_title('10.000 ejecuciones por consulta y etapa · 16/10/2026')
    axis.set_ylim(0, 17)
    axis.legend(frameon=False, loc='upper right')
    axis.spines[['top', 'right']].set_visible(False)
    axis.grid(axis='y', alpha=0.15)
    axis.set_axisbelow(True)
    figure.tight_layout()
    target = root / 'docs/figuras/latencia_antes_despues.svg'
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, metadata={'Date': None})
    plt.close(figure)
    print(target)


if __name__ == '__main__':
    main()
