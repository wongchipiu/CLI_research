'use client';

/* eslint-disable jsx-a11y/label-has-associated-control */

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Database,
  FileJson2,
  FlaskConical,
  LineChart,
  LockKeyhole,
  Play,
  Radar,
  ShieldCheck,
  TrendingUp,
  WalletCards,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function PageIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary/70">{eyebrow}</p>
      <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}

function CommandPreview({ children, label = '对应命令' }: { children: string; label?: string }) {
  return (
    <div className="rounded-xl bg-slate-950 p-4 text-slate-100">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-teal-300">{label}</p>
      <code className="block break-all font-mono text-xs leading-6">{children}</code>
    </div>
  );
}

export function DataPage({ expertMode }: { expertMode: boolean }) {
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Data foundation" title="数据中心" description="先确认数据覆盖和质量，再开展任何收益研究。更新会联网并写入本地行情，质量检查则只读。" />
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-teal-50 text-teal-800"><Database className="size-5" /></div>
            <CardTitle>行情数据更新</CardTitle>
            <CardDescription>选择市场、股票池和可选日期范围。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium">市场<NativeSelect className="w-full"><NativeSelectOption value="us">美股</NativeSelectOption><NativeSelectOption value="cn">A 股</NativeSelectOption><NativeSelectOption value="all">全部</NativeSelectOption></NativeSelect></label>
              <label className="space-y-1.5 text-xs font-medium">股票池<NativeSelect className="w-full"><NativeSelectOption value="baseline">baseline</NativeSelectOption><NativeSelectOption value="extended">extended</NativeSelectOption></NativeSelect></label>
              <label className="space-y-1.5 text-xs font-medium">开始日期（可选）<Input type="date" /></label>
              <label className="space-y-1.5 text-xs font-medium">结束日期（可选）<Input type="date" /></label>
            </div>
            {expertMode && <CommandPreview>.venv/bin/python scripts/update_data.py --market us --universe baseline</CommandPreview>}
            <Button disabled className="w-full"><Play data-icon="inline-start" />连接本地桥接后更新</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-blue-50 text-blue-800"><CheckCircle2 className="size-5" /></div>
            <CardTitle>当前质量状态</CardTitle>
            <CardDescription>页面只读取质量摘要，不加载原始行情。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[['市场', '美股'], ['股票池', 'baseline'], ['标的数量', '待连接'], ['最后检查', '待连接']].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>
              ))}
            </div>
            <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              没有质量摘要时，研究与雷达运行按钮应保持锁定。
            </div>
            {expertMode && <CommandPreview>.venv/bin/python scripts/check_data.py --market us --quiet</CommandPreview>}
            <Button variant="outline" disabled className="w-full">运行只读质量检查</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function ResearchPage({ expertMode }: { expertMode: boolean }) {
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Research studio" title="策略研究" description="把策略、市场、时间边界和参数网格变成一份可审计实验。默认先预览边界，再确认是否消耗最终测试。" />
      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,.8fr)]">
        <Card>
          <CardHeader className="border-b">
            <CardTitle>研究配置</CardTitle>
            <CardDescription>推荐使用统一 workflow；探索回测仅用于训练区间内试验。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 pt-1">
            <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="space-y-1.5 text-xs font-medium">研究类型<NativeSelect className="w-full"><NativeSelectOption>正式验证工作流</NativeSelectOption><NativeSelectOption>探索性回测</NativeSelectOption><NativeSelectOption>仅预览实验边界</NativeSelectOption></NativeSelect></label>
              <label className="space-y-1.5 text-xs font-medium">市场<NativeSelect className="w-full"><NativeSelectOption value="us">美股</NativeSelectOption><NativeSelectOption value="cn">A 股</NativeSelectOption></NativeSelect></label>
              <label className="space-y-1.5 text-xs font-medium">策略<NativeSelect className="w-full"><NativeSelectOption>momentum</NativeSelectOption><NativeSelectOption>momentum_vol</NativeSelectOption><NativeSelectOption>relative_strength</NativeSelectOption><NativeSelectOption>trend_momentum</NativeSelectOption><NativeSelectOption>sma_cross</NativeSelectOption><NativeSelectOption>boll_revert</NativeSelectOption></NativeSelect></label>
              <label className="space-y-1.5 text-xs font-medium">开始日期<Input type="date" defaultValue="2018-01-01" /></label>
              <label className="space-y-1.5 text-xs font-medium">结束日期<Input type="date" defaultValue="2026-07-20" /></label>
              <label className="space-y-1.5 text-xs font-medium">实验文件<Input defaultValue="momentum_001.json" /></label>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold">参数网格</p><Button variant="ghost" size="xs">添加参数</Button></div>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="space-y-1.5 text-xs text-muted-foreground">lookback<Input defaultValue="60,120,250" /></label>
                <label className="space-y-1.5 text-xs text-muted-foreground">top_n<Input defaultValue="1,2" /></label>
                <label className="space-y-1.5 text-xs text-muted-foreground">rebalance<Input defaultValue="20" /></label>
              </div>
            </div>

            <div className="rounded-xl border bg-muted/30 p-4">
              <div className="mb-3 flex items-center justify-between"><p className="text-xs font-semibold">时间切分预览</p><Badge variant="outline">尚未冻结</Badge></div>
              <div className="flex h-3 overflow-hidden rounded-full"><div className="w-3/5 bg-teal-600" /><div className="w-1/5 bg-blue-500" /><div className="w-1/5 bg-orange-500" /></div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]"><span><strong className="text-teal-800">60%</strong> 训练</span><span><strong className="text-blue-700">20%</strong> 验证</span><span><strong className="text-orange-700">20%</strong> 最终测试</span></div>
            </div>

            {expertMode && <CommandPreview>.venv/bin/quant workflow --workspace config/workspace.yaml --strategy momentum --market us --universe baseline --start 2018-01-01 --end 2026-07-20 --study-file momentum_001.json -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 --walk-forward</CommandPreview>}

            <div className="flex flex-col gap-3 sm:flex-row">
              <Button variant="outline" disabled className="flex-1"><CalendarDays data-icon="inline-start" />先预览边界</Button>
              <Button disabled className="flex-1"><LockKeyhole data-icon="inline-start" />确认后正式运行</Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card className="border-orange-200 bg-orange-50/70">
            <CardHeader><CardTitle className="flex items-center gap-2 text-orange-950"><LockKeyhole className="size-4" />最终测试保护</CardTitle><CardDescription className="text-orange-900/70">页面不能把“运行成功”误写成“策略有效”。</CardDescription></CardHeader>
            <CardContent className="space-y-3 text-xs leading-5 text-orange-950/80">
              <p>1. 先预览训练、验证、最终测试的日期边界。</p><p>2. 参数只允许在训练段选择。</p><p>3. 正式运行前必须明确确认会消耗最终测试。</p><p>4. 实验完成后直接读保存结果，不反复试探同一区间。</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>风险覆盖（可选）</CardTitle><CardDescription>控制单一仓位、总敞口、目标波动和风险关闭仓位。</CardDescription></CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-1">
              <label className="space-y-1.5 text-xs font-medium">最大单仓权重<Input placeholder="例如 0.20" /></label>
              <label className="space-y-1.5 text-xs font-medium">最大总敞口<Input placeholder="例如 1.00" /></label>
              <label className="space-y-1.5 text-xs font-medium">目标波动率<Input placeholder="例如 0.12" /></label>
              <label className="space-y-1.5 text-xs font-medium">风险关闭敞口<Input placeholder="例如 0.00" /></label>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export function RadarPage({ expertMode }: { expertMode: boolean }) {
  const command = '.venv/bin/quant scan --workspace config/workspace.yaml --market us --profile momentum_volume';
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Daily watchlist" title="每日美股雷达" description="扫描配置中的固定美股自选池，按量比、1/5/20 日动量和 20/60 日突破形成确定性排名。" />
      <Card>
        <CardHeader className="border-b"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>扫描控制</CardTitle><CardDescription>本地扫描，不联网、不下单。</CardDescription></div><Badge variant="outline">描述性排名</Badge></div></CardHeader>
        <CardContent className="space-y-4 pt-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <label className="space-y-1.5 text-xs font-medium">配置档案<NativeSelect className="w-full"><NativeSelectOption>momentum_volume</NativeSelectOption></NativeSelect></label>
            <label className="space-y-1.5 text-xs font-medium">信号日期<Input type="date" placeholder="默认最新日期" /></label>
            <Button disabled className="self-end"><Radar data-icon="inline-start" />连接后扫描</Button>
          </div>
          {expertMode && <CommandPreview>{command}</CommandPreview>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="border-b"><CardTitle>今日排名</CardTitle><CardDescription>等待本地桥接后读取最近的 scan.json。普通阈值未通过不等于数据故障。</CardDescription></CardHeader>
        <CardContent className="px-0">
          <Table><TableHeader><TableRow><TableHead className="pl-4">排名</TableHead><TableHead>代码</TableHead><TableHead>量比</TableHead><TableHead>1 日动量</TableHead><TableHead>20 日动量</TableHead><TableHead>突破</TableHead><TableHead className="pr-4 text-right">状态</TableHead></TableRow></TableHeader><TableBody><TableRow><TableCell colSpan={7} className="h-32 text-center text-muted-foreground">尚无可显示的雷达扫描</TableCell></TableRow></TableBody></Table>
        </CardContent>
      </Card>
      <div className="grid gap-3 sm:grid-cols-5">
        {[1, 3, 5, 10, 20].map((days) => <div key={days} className="rounded-xl border bg-card p-4"><p className="text-xs text-muted-foreground">信号后</p><p className="mt-1 text-lg font-semibold">{days} 日</p><p className="mt-2 text-xs text-muted-foreground">等待成熟样本</p></div>)}
      </div>
    </div>
  );
}

export function ResultsPage({ expertMode }: { expertMode: boolean }) {
  const rows = [
    ['训练', '2020-01-01—2021-05-18', '142.88%', '86.11%', '6.102', '-0.80%', '0'],
    ['验证', '2021-05-19—2021-11-02', '34.59%', '86.62%', '6.073', '-0.80%', '0'],
    ['最终测试', '2021-11-03—2022-04-19', '34.59%', '86.62%', '6.073', '-0.80%', '0'],
  ];
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Evidence center" title="结果中心" description="统一阅读 metrics.json、参数排名与验证结论。先看结果身份和样本，再看收益数字。" />
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><AlertTriangle className="mt-0.5 size-5 shrink-0" /><div><p className="font-semibold">当前示例是合成教程结果</p><p className="mt-1 text-xs leading-5 text-amber-900/75">synthetic_data=true 且 completed_trades=0；只能用于练习页面阅读，不能说明策略有效。</p></div></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[['最佳参数', 'lookback 10', 'top_n 1 · rebalance 10'], ['最终测试状态', 'Completed', '只表示已运行'], ['相对基准 CAGR', '-0.39%', '未跑赢基准'], ['完整交易', '0', '存在只买未卖']].map(([label, value, hint]) => <Card key={label} size="sm"><CardContent><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{hint}</p></CardContent></Card>)}
      </div>
      <Card>
        <CardHeader className="border-b"><div className="flex items-center justify-between"><div><CardTitle>三段验证对比</CardTitle><CardDescription>各段初始净值独立，不要把滚动折简单拼接为连续收益。</CardDescription></div><Button variant="outline" size="sm"><FileJson2 data-icon="inline-start" />原始 JSON</Button></div></CardHeader>
        <CardContent className="px-0"><Table><TableHeader><TableRow><TableHead className="pl-4">区间</TableHead><TableHead>日期</TableHead><TableHead>总收益</TableHead><TableHead>CAGR</TableHead><TableHead>Sharpe</TableHead><TableHead>最大回撤</TableHead><TableHead className="pr-4">完整交易</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row[0]}>{row.map((value, index) => <TableCell key={value} className={index === 0 ? 'pl-4 font-medium' : index === 6 ? 'pr-4' : ''}>{value}</TableCell>)}</TableRow>)}</TableBody></Table></CardContent>
      </Card>
      {expertMode && <CommandPreview>PYTHONPATH=../gpt_quant/src .venv/bin/python -m gpt_quant.cli validate-cli-result /absolute/path/to/metrics.json</CommandPreview>}
    </div>
  );
}

export function PaperPage({ expertMode }: { expertMode: boolean }) {
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Paper observation" title="模拟账户" description="只有通过研究验证的证据才能初始化模拟账本。信号、价格时点和证据哈希都会被校验。" />
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Card className="border-dashed">
          <CardContent className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
            <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-800"><WalletCards className="size-6" /></div>
            <h3 className="font-semibold">尚未连接模拟账本</h3>
            <p className="mt-2 max-w-sm text-xs leading-5 text-muted-foreground">选择一份验证通过的 metrics.json，设置初始现金后创建本地状态文件。</p>
            <Button disabled className="mt-5">选择证据并初始化</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>安全执行链</CardTitle><CardDescription>页面不会从回测结果直接跳到订单。</CardDescription></CardHeader>
          <CardContent className="space-y-2">
            {['验证研究证据', '初始化并绑定证据哈希', '生成次日开盘目标信号', '校验执行时点与价格新鲜度', '模拟成交并留下审计记录', '持续估值与人工复核'].map((step, index) => <div key={step} className="flex items-center gap-3 rounded-lg border p-3"><span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary font-mono text-xs font-semibold">{index + 1}</span><span className="text-sm">{step}</span>{index < 5 && <ArrowRight className="ml-auto size-4 text-muted-foreground" />}</div>)}
          </CardContent>
        </Card>
      </div>
      {expertMode && <CommandPreview>PYTHONPATH=../gpt_quant/src .venv/bin/python -m gpt_quant.cli paper-report /absolute/path/to/paper-state.json</CommandPreview>}
    </div>
  );
}

export function RiskPage({ expertMode }: { expertMode: boolean }) {
  const levels = [
    ['NORMAL', '正常观察', '不采取账户动作', 'bg-teal-500'],
    ['FREEZE', '冻结新动作', '撤销未完成订单，不再增加风险', 'bg-amber-400'],
    ['REDUCE', '降低风险', '按规则减少持仓', 'bg-orange-500'],
    ['LIQUIDATE', '清仓处置', '关闭持仓并记录完整审计', 'bg-red-600'],
  ];
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Risk control" title="风险控制" description="风险页默认只做配置检查和状态展示。任何连接账户或处置动作都必须通过明确的二次确认。" />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,.8fr)]">
        <Card>
          <CardHeader className="border-b"><CardTitle>风险状态阶梯</CardTitle><CardDescription>系统按已配置阈值逐级升级，不能由语言模型自行降低标准。</CardDescription></CardHeader>
          <CardContent className="space-y-3 pt-4">
            {levels.map(([level, title, description, color]) => <div key={level} className="grid gap-3 rounded-xl border p-4 sm:grid-cols-[130px_1fr]"><div className="flex items-center gap-2"><span className={`size-2.5 rounded-full ${color}`} /><strong className="font-mono text-xs">{level}</strong></div><div><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-xs text-muted-foreground">{description}</p></div></div>)}
          </CardContent>
        </Card>
        <div className="space-y-5">
          <Card><CardHeader><div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-teal-50 text-teal-800"><ShieldCheck className="size-5" /></div><CardTitle>本机预检</CardTitle><CardDescription>不连接 TWS，仅检查配置、目录、依赖与运行模式。</CardDescription></CardHeader><CardContent className="space-y-3">{expertMode && <CommandPreview>.venv/bin/python scripts/run_live_risk.py --config config/live_risk.paper.yaml --preflight</CommandPreview>}<Button disabled variant="outline" className="w-full">连接后执行预检</Button></CardContent></Card>
          <Card className="border-red-200 bg-red-50/70"><CardHeader><CardTitle className="flex items-center gap-2 text-red-950"><LockKeyhole className="size-4" />账户连接已锁定</CardTitle><CardDescription className="text-red-900/70">正式连接前必须通过预检、确认 paper 配置，并输入二次确认文本。</CardDescription></CardHeader><CardContent><Button disabled variant="destructive" className="w-full">读取一次账户快照</Button></CardContent></Card>
        </div>
      </div>
    </div>
  );
}

export function SpecialtyPage({ expertMode }: { expertMode: boolean }) {
  const tools = [
    { icon: LineChart, title: '股票事件研究', description: '比较事件日前后个股、SPY 与同行的表现。', command: '.venv/bin/python scripts/analyze_stock_event.py --symbol AAPL --benchmark SPY --event-date 2026-07-30' },
    { icon: TrendingUp, title: '品牌复利公司评分', description: '结构化评估品牌、增长、需求、扩张、盈利质量和估值。', command: '.venv/bin/python scripts/score_brand_compounders.py --input config/brand_compounders.json --compact' },
    { icon: BarChart3, title: '资产增长复盘', description: '根据资产流水比较当前进度与目标差距。', command: '.venv/bin/python scripts/review_asset_growth.py config/asset_ledger.csv --target 1000000' },
    { icon: FlaskConical, title: 'Agent 工具演示', description: '不需要 API Key，演示行情工具和审计循环。', command: 'PYTHONPATH=../gpt_quant/src .venv/bin/python -m gpt_quant.cli agent-demo' },
  ];
  return (
    <div className="space-y-5">
      <PageIntro eyebrow="Special studies" title="专项分析" description="把事件研究、公司评分、资产复盘和 Agent 演示放在独立工具区，不与正式策略准入混为一谈。" />
      <div className="grid gap-5 lg:grid-cols-2">
        {tools.map(({ icon: Icon, title, description, command }) => <Card key={title}><CardHeader><div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-secondary text-secondary-foreground"><Icon className="size-5" /></div><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent className="space-y-4">{expertMode && <CommandPreview>{command}</CommandPreview>}<Button disabled variant="outline" className="w-full">配置并运行</Button></CardContent></Card>)}
      </div>
    </div>
  );
}
