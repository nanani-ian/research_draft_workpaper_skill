// Style a source-bound Artifact Tool line or column chart. No I/O or data edits.
export function applyBasicChartStyle(chart, {
  kind = 'line', font = 'Microsoft YaHei',
  palette = ['#C00000', '#0070C0', '#9FA7B2'],
  numberFormat = '0.0', legend = chart.series.items.length > 1,
} = {}) {
  if (!['line', 'bar'].includes(kind)) throw new Error('Style helper supports line or column only.');
  if (!palette.length) throw new Error('Provide at least one series color.');
  chart.chartFill = {type:'none'};
  chart.plotAreaFill = {type:'none'};
  chart.chartArea.format.line.visible = false;
  chart.plotArea.format.line.visible = false;
  chart.titleTextStyle.typeface = font;
  chart.titleTextStyle.fontSize = 15;
  chart.titleTextStyle.bold = true;
  chart.hasLegend = legend;
  if (legend) chart.legend = {position:'top', textStyle:{typeface:font, fontSize:12}};
  chart.xAxis = {
    axisType:'textAxis', textStyle:{typeface:font, fontSize:12},
    majorGridlines:null, minorGridlines:null,
    line:{fill:'#B0B0B0', style:'solid', width:1},
  };
  chart.yAxis = {
    numberFormatCode:numberFormat, numberFormatSourceLinked:false,
    textStyle:{typeface:font, fontSize:12},
    majorGridlines:{fill:'#E7E7E7', style:'solid', width:0.5},
    minorGridlines:null, line:{fill:'#B0B0B0', style:'solid', width:1},
  };
  if (kind === 'bar') {
    chart.barOptions.direction = 'column';
    chart.barOptions.grouping = 'clustered';
    chart.barOptions.gapWidth = 100;
  }
  chart.series.items.forEach((series, i) => {
    const color = palette[i % palette.length];
    series.fill = color;
    series.line = {fill:color, style:'solid', width:kind === 'line' ? 2 : 0.5};
  });
  return chart;
}
