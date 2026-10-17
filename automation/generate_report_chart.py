#!/usr/bin/env python3
"""Generate independent before/after charts for every query in the final report."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    root = Path(__file__).resolve().parent.parent
    with (root / 'evidencias/comparacion_carga.csv').open(encoding='utf-8') as handle:
        records = {(row['case'], row['stage']): float(row['median_ms']) for row in csv.DictReader(handle)}
    names = {'Q1': 'Pedidos pendientes', 'Q2': 'Conciliación de pagos',
             'Q3': 'Ranking de productos', 'Q4': 'Clientes para CRM', 'Q5': 'Reporte regional'}
    for case, name in names.items():
        figure, axis = plt.subplots(figsize=(6.4, 3.4))
        values = [records[(case, stage)] for stage in ('A', 'C')]
        bars = axis.bar(['Antes · A', 'Después · C'], values, width=0.5,
                        color=['#64748b', '#0f766e'])
        axis.bar_label(bars, labels=[f'{value:.3f}'.replace('.', ',') for value in values],
                       padding=5, fontsize=11)
        axis.set_ylabel('Mediana del tiempo del cliente (ms)')
        axis.set_title(f'{case} · {name}\n10.000 ejecuciones por etapa · 16/10/2026')
        axis.set_ylim(0, max(values) * 1.25)
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='y', alpha=0.15)
        axis.set_axisbelow(True)
        figure.tight_layout()
        target = root / f'docs/figuras/{case}_antes_despues'
        target.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(target.with_suffix('.svg'), metadata={'Date': None})
        figure.savefig(target.with_suffix('.png'), dpi=160)
        plt.close(figure)
        print(target.with_suffix('.png'))


if __name__ == '__main__':
    main()
