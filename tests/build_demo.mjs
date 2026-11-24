// Rebuild the synthetic example only; never use this as a general workbook editor.
// Args: bundled node_modules path, new XLSX output path, existing preview directory.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {applyBasicChartStyle} from '../scripts/excel_chart_style.mjs';
const [dependencies, output, previewDir] = process.argv.slice(2);
if (!dependencies || !output || !previewDir) throw new Error('Need node_modules, new output path and preview directory');
try { await fs.access(output); throw new Error('Output exists; refusing overwrite'); }
catch (e) { if (e.code !== 'ENOENT') throw e; }
const require = createRequire(path.join(path.resolve(dependencies), '_research_resolver.cjs'));
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const wb = Workbook.create();
const colors = {ink:'#243746', blue:'#DDE7F2', green:'#E4EEE8', note:'#586875', input:'#245DA8'};
const sheets = ['主体跟踪','专题模块','驱动测算','定期图表'].map(name => wb.worksheets.add(name));
for (const sh of sheets) {
  sh.showGridLines = false;
  sh.getRange('A1:N38').format.font = {name:'Microsoft YaHei',size:10,color:colors.ink};
  sh.getRange('A1:N38').format.rowHeight = 23;
  sh.getRange('A1:A38').format.columnWidth = 3;
  sh.getRange('B1:B38').format.columnWidth = 32;
  sh.getRange('C1:G38').format.columnWidth = 15;
  sh.getRange('H1:H38').format.columnWidth = 3;
  sh.getRange('I1:N38').format.columnWidth = 13;
  sh.getRange('B2').values = [[sh.name==='专题模块'?'专题研究模块演示':sh.name+'模块演示']];
  sh.getRange('B2').format.font = {name:'Microsoft YaHei',size:14,bold:true,color:colors.ink};
  sh.getRange('B4').values = [['虚构示例；表头、指标及行列按问题和资料调整；四页独立，可按需组合。']];
  sh.getRange('B4').format.font = {name:'Microsoft YaHei',size:10,color:colors.note};
}
function header(sh,address){const r=sh.getRange(address);r.format.fill=colors.blue;r.format.font.bold=true;r.format.wrapText=true;r.format.rowHeight=38;r.format.horizontalAlignment='center';r.format.verticalAlignment='center';}
function chart(sh,range,title,start,end,kind='line',opts={}){
  const ranges=Array.isArray(range)?range.map(r=>sh.getRange(r)):sh.getRange(range);
  const c=sh.charts.add(kind,ranges);c.title=title;c.setPosition(start,end);
  applyBasicChartStyle(c,{kind,...opts});return c;
}

const entity=sheets[0];
entity.getRange('B6:F9').values=[['主体','原数期间','更新状态','期间口径','来源属性'],['甲公司','2025全年','待增补中期','自然年度','虚构演示'],['乙公司','2025财年','待对齐期间','财年截至6月','虚构演示'],['丙公司','2025全年','已录入演示值','自然年度','虚构演示']];
header(entity,'B6:F6');
entity.getRange('B12:F15').values=[['主体','2024产量（万吨）','2025产量（万吨）','同比','2025成本（元/吨）'],['甲公司',10,12,null,110],['乙公司',8,9,null,125],['丙公司',6,7,null,130]];
header(entity,'B12:F12');
for(let r=13;r<=15;r++)entity.getRange(`E${r}`).formulas=[[`=D${r}/C${r}-1`]];
entity.getRange('E13:E15').setNumberFormat('0.0%');
entity.getRange('C13:D15').format.font.color=colors.input;
entity.getRange('B18').values=[['更新状态与横向指标同页；复杂主体明细可另表，汇总引用同一原数。']];
entity.getRange('F1:F38').format.columnWidth=20;
chart(entity,'B12:D15','主体产量比较（万吨）','I6','O20','bar');

const theme=sheets[1];
theme.getRange('B6:F10').values=[['年度','产能（万吨）','利用率','理论产出（万吨）','披露产量（万吨）'],[2023,10,.8,null,7.8],[2024,12,.85,null,10],[2025,14,.9,null,12.3],[2026,16,.9,null,14.2]];
header(theme,'B6:F6');
for(let r=7;r<=10;r++)theme.getRange(`E${r}`).formulas=[[`=C${r}*D${r}`]];
theme.getRange('D7:D10').setNumberFormat('0.0%');theme.getRange('E7:F10').setNumberFormat('0.0');
theme.getRange('B13:E17').values=[['年度','理论与披露差额（万吨）','披露产量同比','属性'],[2023,null,null,'演示输入'],[2024,null,null,'演示输入'],[2025,null,null,'演示输入'],[2026,null,null,'演示输入']];
header(theme,'B13:E13');
for(let r=14;r<=17;r++){theme.getRange(`C${r}`).formulas=[[`=E${r-7}-F${r-7}`]];if(r>14)theme.getRange(`D${r}`).formulas=[[`=F${r-7}/F${r-8}-1`]];}
theme.getRange('C14:C17').setNumberFormat('0.00');theme.getRange('D15:D17').setNumberFormat('0.0%');
theme.getRange('B20').values=[['来源：虚构数据。理论产出为计算值，不能替代披露产量。']];
// Formula-backed year labels keep numeric years from showing thousands separators.
theme.getRange('B23:E23').values=[['绘图年份','理论产出','披露产量','利用率']];
header(theme,'B23:E23');
for(let r=24;r<=27;r++)theme.getRange(`B${r}:E${r}`).formulas=[[`=TEXT(B${r-17},"0")`,`=E${r-17}`,`=F${r-17}`,`=D${r-17}`]];
theme.getRange('C24:D27').setNumberFormat('0.0');theme.getRange('E24:E27').setNumberFormat('0%');
chart(theme,'B23:D27','理论与披露产出（万吨）','I6','O18','bar');
chart(theme,['B23:B27','E23:E27'],'产能利用率（%）','I21','O33','line',{numberFormat:'0%',palette:['#C00000']});

const model=sheets[2];
model.getRange('B6:E11').values=[['指标','2025实际（演示）','2026预测（演示）','类型／单位'],['终端数量',100,120,'万件；右列为假设'],['替代渗透率',.1,.15,'比例；右列为假设'],['单位耗量',2,2,'kg/件；演示参数'],['材料需求',null,null,'万吨；公式结果'],['同比',null,null,'比例；公式结果']];
header(model,'B6:E6');model.getRange('C8:D8').setNumberFormat('0.0%');
model.getRange('C10').formulas=[['=C7*C8*C9/1000']];model.getRange('D10').formulas=[['=D7*D8*D9/1000']];model.getRange('D11').formulas=[['=D10/C10-1']];
model.getRange('C10:D10').setNumberFormat('0.000');model.getRange('D11').setNumberFormat('0.0%');
model.getRange('C7:D9').format.font.color=colors.input;
model.getRange('E1:E38').format.columnWidth=26;
model.getRange('C7:D11').format.horizontalAlignment='center';
model.getRange('B14').values=[['换算：万件 × kg/件 = 10吨；转换为万吨需除以1000。']];
model.getRange('B16').values=[['参数说明：所有输入均为演示值；正式使用须登记假设依据及数据截图。']];
model.getRange('B18').values=[['读取顺序：终端数量 → 替代渗透率 → 单位耗量 → 材料需求。']];

const periodic=sheets[3];
periodic.getRange('B6:D12').values=[['日期','原始值（点）','来源属性'],[new Date('2025-12-05T00:00:00Z'),90,'虚构演示'],[new Date('2025-12-12T00:00:00Z'),95,'虚构演示'],[new Date('2026-01-02T00:00:00Z'),100,'虚构演示'],[new Date('2026-01-09T00:00:00Z'),null,'缺测，不补0'],[new Date('2026-01-16T00:00:00Z'),0,'演示中的有效0'],[new Date('2026-01-23T00:00:00Z'),110,'虚构演示']];
header(periodic,'B6:D6');periodic.getRange('B7:B12').setNumberFormat('yyyy-mm-dd');
periodic.getRange('F6:G10').values=[['绘图日期','绘图值（点）'],[null,null],[null,null],[null,null],[null,null]];
header(periodic,'F6:G6');
for(let r=7;r<=10;r++){periodic.getRange(`F${r}`).formulas=[[`=TEXT(B${r+2},"yyyy-mm-dd")`]];periodic.getRange(`G${r}`).formulas=[[`=IF(ISNUMBER(C${r+2}),C${r+2},NA())`]];}
periodic.getRange('B16').values=[['原始历史保留；图源只引用2026年窗口。#N/A为明确缺测标记。']];
periodic.getRange('B18').values=[['有效0与缺失分开；窗口扩展需检查图源和原生图表引用范围。']];
const recent=chart(periodic,'F6:G10','近期窗口（点）','I6','O20','line',{numberFormat:'0',palette:['#C00000']});
recent.dataLabels={showValue:true,position:'outEnd',textStyle:{typeface:'Microsoft YaHei',fontSize:11}};

// Exercise the calculation chain in memory, then restore the delivered example.
wb.recalculate();
assert.ok(Math.abs(model.getRange('C10').values[0][0]-.02)<1e-10);
model.getRange('C7').values=[[200]];
wb.recalculate();
assert.ok(Math.abs(model.getRange('C10').values[0][0]-.04)<1e-10);
assert.ok(Math.abs(model.getRange('D11').values[0][0]+.1)<1e-10);
model.getRange('C7').values=[[100]];
wb.recalculate();
assert.ok(Math.abs(model.getRange('D11').values[0][0]-.8)<1e-10);
for(const sh of sheets){
 const inspect=await wb.inspect({kind:'region',sheetId:sh.name,range:'B6:G18',maxChars:700,tableMaxRows:3,tableMaxCols:4});
 console.log(sh.name,inspect.ndjson);
 const preview=await wb.render({sheetName:sh.name,range:sh.name==='专题模块'?'A1:O35':'A1:O23',scale:1,format:'png'});
 await fs.writeFile(path.join(previewDir,`${sh.name}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log('MODEL',sheets[2].getRange('C10:D11').values);
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
console.log('SAVED',output);
