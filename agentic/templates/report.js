const data = JSON.parse(document.getElementById('report-data').textContent);
const tabs = [...document.querySelectorAll('[data-tab]')];
for (const tab of tabs) tab.addEventListener('click', () => {
  for (const b of tabs) { b.setAttribute('aria-selected', String(b === tab)); b.tabIndex = b === tab ? 0 : -1; }
  for (const panel of document.querySelectorAll('[data-panel]')) panel.hidden = panel.dataset.panel !== tab.dataset.tab;
});
for (const [index, tab] of tabs.entries()) {
  tab.tabIndex = index === 0 ? 0 : -1;
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) { event.preventDefault(); tabs[next].click(); tabs[next].focus(); }
  });
}
const dialog = document.getElementById('source-dialog');
for (const button of document.querySelectorAll('[data-source]')) button.addEventListener('click', () => {
  const source = data.report.case.sources.find(s => s.source_id === button.dataset.source);
  document.getElementById('source-title').textContent = source.source_id + ' · ' + source.speaker;
  document.getElementById('source-quote').textContent = source.text;
  document.getElementById('source-meta').textContent = source.locator + ' / ' + (source.time || '日期未知') + ' / 精度：' + source.time_precision;
  document.getElementById('source-hash').textContent = data.report.ledger.facts.find(f => f.source_id === source.source_id).source_digest;
  dialog.showModal();
});
document.getElementById('source-close').addEventListener('click', () => dialog.close());
for (const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click', () => {
  for (const b of document.querySelectorAll('[data-filter]')) b.setAttribute('aria-pressed', String(b === button));
  for (const card of document.querySelectorAll('[data-gap]')) card.hidden = button.dataset.filter !== 'all' && card.dataset.status !== button.dataset.filter;
});
document.getElementById('source-search').addEventListener('input', event => {
  const query = event.target.value.trim().toLocaleLowerCase();
  let shown = 0;
  for (const row of document.querySelectorAll('[data-fact]')) {
    row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
    if (!row.hidden) shown++;
  }
  document.getElementById('search-count').textContent = '显示 ' + shown + ' 条材料';
});
document.getElementById('print-report').addEventListener('click', () => window.print());
document.getElementById('download-data').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = 'report-data.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
