"""Readable, standalone plotting code for the notebook."""


def customize_code(code, options):
    code = code.replace('bins=15', f"bins={int(options.get('bins',15))}")
    for color in ('#22965e', '#188650'):
        code = code.replace(repr(color), repr(options.get('color',color)))
    commands = [f"    _ax.set_xscale({options.get('xscale','linear')!r})", f"    _ax.set_yscale({options.get('yscale','linear')!r})"]
    for key in ('title','xlabel','ylabel'):
        if options.get(key):
            commands.append(f"    _ax.set_{key}({options[key]!r})")
    snippet = 'for _ax in plt.gcf().axes:\n'+'\n'.join(commands)+'\n'
    # Match indentation for the histogram's multi-figure loop.
    return code.replace('    plt.show()', '\n'.join('    '+line for line in snippet.splitlines())+'\n    plt.show()') if '    plt.show()' in code else code.replace('plt.show()',snippet+'plt.show()')


def histogram_code():
    # Four variables per figure keeps a large selection from shrinking every panel.
    return '''from matplotlib.ticker import MaxNLocator

# Keep 15 bins; only the layout and tick formatting change.
if len(numeric.columns) == 0:
    raise ValueError('Select numeric columns / Sélectionnez des colonnes numériques')

plt.rcParams.update({
    'font.size': 11, 'axes.titlesize': 12, 'axes.labelsize': 11,
    'xtick.labelsize': 10, 'ytick.labelsize': 10,
    'axes.edgecolor': '#444444', 'grid.color': '#b8b8b8',
})
for start in range(0, len(numeric.columns), 4):
    chart_columns = list(numeric.columns[start:start + 4])
    columns_per_row = min(2, len(chart_columns))
    rows = (len(chart_columns) + columns_per_row - 1) // columns_per_row
    fig, axes = plt.subplots(
        rows, columns_per_row, squeeze=False,
        figsize=(12 if columns_per_row == 2 else 9, 3.8 * rows + 0.5),
        layout='constrained',
    )
    fig.get_layout_engine().set(w_pad=0.08, h_pad=0.10, wspace=0.12, hspace=0.16)
    for ax, column in zip(axes.flat, chart_columns):
        values = numeric[column].dropna()
        ax.hist(values, bins=15, color='#22965e', edgecolor='white', linewidth=0.6)
        ax.set_title(str(column), pad=10)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, min_n_ticks=3))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True, min_n_ticks=3))
        ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        ax.tick_params(axis='both', pad=4)
        ax.grid(True, linewidth=0.7, alpha=0.75)
        ax.set_axisbelow(True)
    for ax in list(axes.flat)[len(chart_columns):]:
        fig.delaxes(ax)
    plt.show()
'''
