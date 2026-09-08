'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  Building2,
  CalendarClock,
  CheckCircle2,
  Database,
  FileSearch,
  Scale,
  Users,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type Horizon = '5' | '20' | '60';

const horizonResults = {
  '5': { purchaseEvents: 394, saleEvents: 401, purchaseExcess: 0.048, saleExcess: -0.0756, difference: 0.1236, interval: [-0.4746, 0.7312], purchasePositive: 47.21 },
  '20': { purchaseEvents: 382, saleEvents: 392, purchaseExcess: -0.2916, saleExcess: -0.5172, difference: 0.2256, interval: [-1.0787, 1.4919], purchasePositive: 43.46 },
  '60': { purchaseEvents: 343, saleEvents: 334, purchaseExcess: 0.0411, saleExcess: -1.2402, difference: 1.2813, interval: [-1.4132, 4.0576], purchasePositive: 44.9 },
} as const;

const periods = [
  { period: '2025 Q4', managers: '1 / 27', publicDate: '2026-02-17', state: '覆盖不完整' },
  { period: '2026 Q1', managers: '27 / 27', publicDate: '2026-05-15', state: '完整基线' },
  { period: '2026 Q2', managers: '27 / 27', publicDate: '2026-08-14', state: '首个变化截面' },
];

function percent(value: number) {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function CommandPreview({ children }: { children: string }) {
  return (
    <div className="rounded-xl bg-slate-950 p-4 text-slate-100">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-teal-300">只读源数据 · 写入研究摘要</p>
      <code className="block break-all font-mono text-xs leading-6">{children}</code>
    </div>
  );
}

export function DisclosureLabPage({ expertMode }: { expertMode: boolean }) {
  const [horizon, setHorizon] = useState<Horizon>('20');
  const result = horizonResults[horizon];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary/70">Disclosure research lab</p>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">公开申报研究实验室</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            把 13F 与国会议员 PTR 改写为可证伪命题，只从真正公开后的下一交易日开始计算，避免把事后信息伪装成可交易信号。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="border-teal-200 bg-teal-50 text-teal-800">本次未下载数据</Badge>
          <Badge variant="outline">快照 2026-08-30 16:20</Badge>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { icon: Building2, label: '13F 申报', value: '97', note: '44 家机构 · 3 个季度' },
          { icon: Users, label: 'Congress PTR', value: '693', note: '610 已解析 · 83 待 OCR' },
          { icon: FileSearch, label: '合并申报事件', value: '4,801', note: '排除修正件与异常日期' },
          { icon: Database, label: '本地行情', value: '50 只', note: '截止 2026-07-20' },
        ].map(({ icon: Icon, label, value, note }) => (
          <Card key={label}>
            <CardContent className="pt-5">
              <div className="flex items-start justify-between gap-3">
                <div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p></div>
                <span className="flex size-9 items-center justify-center rounded-xl bg-secondary text-secondary-foreground"><Icon className="size-4" /></span>
              </div>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">{note}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden border-0 shadow-[0_12px_40px_rgb(15_35_42/7%)] ring-border">
        <CardHeader className="border-b bg-[#0d2e34] text-white">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><Scale className="size-4 text-teal-300" />命题一：国会议员买入申报是否优于卖出？</CardTitle>
              <CardDescription className="mt-1 text-teal-50/65">H0：买入公开后的超额收益不高于卖出；H1：买入高于卖出。</CardDescription>
            </div>
            <Badge className="bg-amber-300 text-amber-950">结论不明确</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-center">
            <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">申报交易发生</p><p className="mt-1 text-sm font-semibold">transaction_date</p><p className="mt-1 text-xs text-red-700">不可作为已知信号</p></div>
            <ArrowRight className="mx-auto hidden size-4 text-muted-foreground md:block" />
            <div className="rounded-xl border border-teal-200 bg-teal-50 p-4"><p className="text-xs text-teal-800/70">公众看到申报</p><p className="mt-1 text-sm font-semibold text-teal-950">filed_date</p><p className="mt-1 text-xs text-teal-800">唯一允许的信号起点</p></div>
            <ArrowRight className="mx-auto hidden size-4 text-muted-foreground md:block" />
            <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">模拟进入</p><p className="mt-1 text-sm font-semibold">下一交易日开盘</p><p className="mt-1 text-xs text-muted-foreground">评估 5 / 20 / 60 日</p></div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-2 text-xs font-semibold text-muted-foreground">选择持有期</span>
            {(['5', '20', '60'] as Horizon[]).map((value) => (
              <Button key={value} size="sm" variant={horizon === value ? 'default' : 'outline'} onClick={() => setHorizon(value)}>{value} 个交易日</Button>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border p-4">
              <p className="text-xs text-muted-foreground">买入事件平均超额</p>
              <p className={`mt-1 text-2xl font-semibold ${result.purchaseExcess >= 0 ? 'text-teal-700' : 'text-red-700'}`}>{percent(result.purchaseExcess)}</p>
              <p className="mt-2 text-xs text-muted-foreground">{result.purchaseEvents} 个事件 · 正超额比例 {result.purchasePositive.toFixed(1)}%</p>
            </div>
            <div className="rounded-xl border p-4">
              <p className="text-xs text-muted-foreground">卖出事件平均超额</p>
              <p className={`mt-1 text-2xl font-semibold ${result.saleExcess >= 0 ? 'text-teal-700' : 'text-red-700'}`}>{percent(result.saleExcess)}</p>
              <p className="mt-2 text-xs text-muted-foreground">{result.saleEvents} 个事件</p>
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-xs text-amber-900/70">买入 − 卖出</p>
              <p className="mt-1 text-2xl font-semibold text-amber-950">{percent(result.difference)}</p>
              <p className="mt-2 text-xs text-amber-900/75">95% 区间 {percent(result.interval[0])} ～ {percent(result.interval[1])}</p>
            </div>
          </div>

          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-800" />
              <div><p className="text-sm font-semibold text-amber-950">不能拒绝 H0</p><p className="mt-1 text-xs leading-5 text-amber-900/75">三个持有期的差值都为正，但置信区间全部跨过 0；而且只匹配到本地 50 只当前大盘股，重叠事件和同股聚类尚未校正。现在不能宣称“跟买议员有效”。</p></div>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between text-xs"><span className="font-semibold">本地行情覆盖</span><span className="text-muted-foreground">928 / 4,801 个事件（19.3%）</span></div>
            <Progress value={19.33} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,.85fr)]">
        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-3"><div><CardTitle>命题二：13F 高共识组合</CardTitle><CardDescription>高共识新建/增持是否在完整公开后跑赢低共识对照。</CardDescription></div><Badge variant="destructive">BLOCKED</Badge></div>
          </CardHeader>
          <CardContent className="px-0">
            <Table>
              <TableHeader><TableRow><TableHead className="pl-4">季度</TableHead><TableHead>机构覆盖</TableHead><TableHead>完整公开日</TableHead><TableHead className="pr-4 text-right">状态</TableHead></TableRow></TableHeader>
              <TableBody>
                {periods.map((row) => <TableRow key={row.period}><TableCell className="pl-4 font-medium">{row.period}</TableCell><TableCell>{row.managers}</TableCell><TableCell>{row.publicDate}</TableCell><TableCell className="pr-4 text-right"><Badge variant={row.state === '首个变化截面' ? 'default' : 'outline'}>{row.state}</Badge></TableCell></TableRow>)}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Ban className="size-4 text-red-700" />为什么系统停止</CardTitle><CardDescription>阻塞是研究结论的一部分，不是需要绕过的程序错误。</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {[
              '只有 1 个由连续完整季度形成的变化截面，无法检验跨季度稳定性。',
              'Q2 信号到 2026-08-14 才完整公开，但本地行情只到 2026-07-20。',
              '仓库以 CUSIP 标识证券，批量回测前还缺带来源与有效期的 ticker 映射。',
            ].map((text) => <div key={text} className="flex items-start gap-3 rounded-lg border p-3"><CalendarClock className="mt-0.5 size-4 shrink-0 text-red-700" /><p className="text-xs leading-5">{text}</p></div>)}
          </CardContent>
        </Card>
      </div>

      <Card className="border-teal-200 bg-teal-50/65">
        <CardContent className="flex flex-col gap-4 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-teal-800" /><div><p className="text-sm font-semibold text-teal-950">本轮严谨答案</p><p className="mt-1 max-w-3xl text-xs leading-5 text-teal-900/75">Congress 信号存在轻微方向差异，但证据不足；13F 暂时不可检验。系统已经能重复生成审计结果，下一步应补本地行情覆盖、CUSIP 映射和跨季度样本，而不是直接给出股票推荐。</p></div></div>
          <Button disabled variant="outline" className="border-teal-300 bg-white/80">本地桥接后刷新</Button>
        </CardContent>
      </Card>

      {expertMode && (
        <CommandPreview>cd /Users/brucehuang/Documents/ChatGPT/crawler &amp;&amp; PYTHONPATH=src /Users/brucehuang/Documents/CLI_research/.venv/bin/python -m disclosurelab --compact</CommandPreview>
      )}
    </div>
  );
}
