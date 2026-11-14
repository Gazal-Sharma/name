// Plain-English explanations, tappable anywhere a term appears. Written for someone with no finance background.
export const TERMS = {
  revenue: ["Revenue", "Total sales: all the money that came in from selling goods or services in the period. It is the top line, before any costs."],
  ebitda: ["EBITDA", "Earnings before interest, tax, depreciation and amortisation. A rough measure of how profitable the core business is, before the effects of loans, taxes and accounting for ageing assets."],
  pbt: ["PBT", "Profit before tax: what is left after all costs and loan interest, but before income tax."],
  pat: ["PAT", "Profit after tax, also called net profit. The bottom line: what is left for shareholders once everything is paid."],
  qoq: ["QoQ", "Quarter on quarter: this three-month period compared with the three months just before it. Useful for momentum, but distorted by seasons (festive quarters look strong)."],
  yoy: ["YoY", "Year on year: this quarter compared with the same quarter a year ago. The usual way to compare, because it removes seasonal effects."],
  margin: ["Margin", "Profit as a share of revenue. An EBITDA margin of 15% means ₹15 of every ₹100 in sales is left as operating profit. Falling margins mean costs are rising faster than sales."],
  nifty: ["Against the Nifty", "The Nifty 50 is an index of India's 50 largest listed companies. If a stock rose 3% on a day the Nifty rose 1%, it beat the market by 2 points. That extra part is what is specific to the company."],
  volume: ["Volume", "How many shares changed hands that day. Volume several times the normal level means far more people than usual were buying or selling, which often signals news."],
  filing: ["Filing", "Listed companies must tell the stock exchange about anything important, in a formal document called a filing or announcement. Most are routine paperwork; a few change what the company is worth."],
  guidance: ["Guidance", "What management itself says it expects in future, such as 'revenue will grow 10 to 12% this year'. FINN records these promises and later checks them against the reported numbers."],
  concall: ["Earnings call", "Every quarter, management holds a phone call with investors to discuss results and answer questions. The written record is called the transcript."],
  crore: ["₹ crore", "One crore is 10 million. ₹21,794 crore is about ₹218 billion. Indian company accounts are reported in crore."],
  consolidated: ["Consolidated", "Numbers for the whole group, including subsidiaries, rather than just the parent company on its own."],
  mcap: ["Market cap", "Share price multiplied by the number of shares: what the stock market says the whole company is worth."],
  pe: ["P/E", "Price to earnings: the share price divided by profit per share. A P/E of 20 means investors pay ₹20 for every ₹1 of yearly profit. Higher usually means faster growth is expected."],
  roce: ["ROCE", "Return on capital employed: profit earned for every ₹100 of money invested in the business. Higher is better."],
  roe: ["ROE", "Return on equity: profit earned for every ₹100 of shareholders' money. Higher is better."],
  cashconv: ["Cash conversion", "Whether reported profit shows up as actual cash. Profit that never becomes cash, year after year, is a warning sign."],
  leverage: ["Leverage", "How much the company has borrowed compared with its own money. More debt means more risk if business slows."],
};
export const CATS = {
  results: "The company's financial results for a quarter or year. The single most important regular filing: it shows whether sales and profit are growing.",
  "M&A": "The company is buying, merging with, selling or splitting off a business. Large deals can change what the company is worth; tiny ones are housekeeping.",
  fund_raise: "The company is raising money by selling new shares or borrowing, or returning money through a buyback. New shares dilute existing owners.",
  management_change: "Someone at the top is joining or leaving. A new chief executive or finance chief matters; a routine board rotation usually does not.",
  litigation: "A lawsuit, tax demand, fine or regulator's order. What matters is the amount compared with the company's size.",
  insider_trading: "Founders or senior insiders buying or selling their own shares. Insiders buying is often read as confidence.",
  earnings_call: "Notices, recordings and transcripts of the quarterly call where management discusses results with investors.",
  investor_meetings: "Schedules of meetings with funds and investor conferences. Almost always routine.",
  credit_rating: "A rating agency's view of how safely the company can repay its debt. A downgrade is a warning; a reaffirmation is routine.",
  dividend: "Cash paid to shareholders out of profit.",
  bonus_split: "The company increases the number of shares without anyone paying. You hold more shares, each worth proportionally less.",
  capex: "Spending on new plants, capacity or other long-term assets. It shows where management expects growth.",
  press_release: "General company news: orders won, product launches, partnerships, and responses to press reports. Most is marketing; a large order is not.",
  postal_ballot: "Shareholders voting by post on a company proposal.",
  agm_egm: "Shareholder meetings: the yearly general meeting or a special one.",
  pledging: "Founders using their own shares as security for a loan. Heavy pledging is a risk: if the price falls, lenders may sell those shares.",
  unclassified: "Routine compliance paperwork, such as employee stock option allotments and certificates. Rarely affects the share price.",
};
export const GUIDE = `<h3>How to read FINN</h3>
<p><b>What it is for.</b> You hold shares in 18 companies. Each of them sends the stock exchange several formal notices a week, called filings. Most are paperwork. FINN reads all of them and shows you the few that could change what a company is worth.</p>
<p style="margin-top:10px"><b>Today.</b> Pick a time window. The big sentence tells you how many filings arrived and how many matter. "Matters" are the important ones, shown in full. "Worth a glance" are one-line items. "Buried" is everything FINN judged routine, with its reason.</p>
<p style="margin-top:10px"><b>Watch.</b> Share prices sometimes jump or fall sharply, or trade far more than usual. You set how big a move counts as unusual, and FINN lists every time it happened and whether a filing explains it.</p>
<p style="margin-top:10px"><b>Research.</b> Type any company. FINN reads what its managers promised on recent investor calls and checks each promise against the results that followed.</p>
<p class="hint" style="margin-top:12px">Tap any dotted-underlined word in the app for a plain explanation.</p>`;
