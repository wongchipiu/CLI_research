'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Ban,
  Calculator,
  CheckCircle2,
  CircleDashed,
  Landmark,
  LockKeyhole,
  Target,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function formatMoney(value: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number, digits = 2) {
  return `${value.toFixed(digits)}%`;
}

function CommandBlock({ children }: { children: string }) {
  return (
    <div className="rounded-xl bg-slate-950 p-4 text-slate-100">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-teal-300">对应命令</p>
      <code className="block break-all font-mono text-xs leading-6">{children}</code>
    </div>
  );
}

export function GoalCasePage({ expertMode }: { expertMode: boolean }) {
  const [accountValue, setAccountValue] = useState(100000);
  const [monthlyTarget, setMonthlyTarget] = useState(10);

  const metrics = useMemo(() => {
    const rate = Math.max(0, monthlyTarget) / 100;
    const monthlyProfit = Math.max(0, accountValue) * rate;
    const annualizedReturn = (Math.pow(1 + rate, 12) - 1) * 100;
    const dailyReturn = (Math.pow(1 + rate, 1 / 21) - 1) * 100;
    const threeMonthReturn = (Math.pow(1 + rate, 3) - 1) * 100;
    const yearEndValue = Math.max(0, accountValue) * Math.pow(1 + rate, 12);
    const months = Array.from({ length: 12 }, (_, index) => ({
      month: index + 1,
      value: Math.max(0, accountValue) * Math.pow(1 + rate, index + 1),
    }));
    return { monthlyProfit, annualizedReturn, dailyReturn, threeMonthReturn, yearEndValue, months };
  }, [accountValue, monthlyTarget]);

  const steps = [
    { title: '读取 IBKR 当前账户基线', state: '阻塞', detail: 'TWS/IB Gateway 未运行；官方 ibapi 未安装；账户配置仍是占位符。' },
    { title: '把目标改写为可检验问题', state: '完成', detail: '不直接问“能否赚 10%”，而是约束时间、费用、执行模型、样本外证据和最大回撤。' },
    { title: '提出原假设与备择假设', state: '完成', detail: 'H0：证据不足或风险超限；H1：独立样本外达到目标且通过全部闸门。' },
    { title: '准备真实数据与历史股票池', state: '待办', detail: '先更新数据并通过质量检查；不能使用合成教程结果。' },
    { title: '冻结参数并运行正式研究', state: '待办', detail: '训练段选参，验证通过后只运行一次最终测试，并保留数据和源码指纹。' },
    { title: '交给 GPT Quant 验证', state: '待办', detail: '检查至少三年数据、样本外完整交易、回撤、Sharpe、Calmar、邻参和 walk-forward。' },
    { title: '进入至少 63 个交易日模拟观察', state: '待办', detail: `若目标为 ${formatPercent(monthlyTarget, 1)}，三个月复利目标约为 ${formatPercent(metrics.threeMonthReturn, 1)}，同时仍要满足风险约束。` },
    { title: '形成答案', state: '当前结论', detail: '目前只能得出“尚无证据支持该目标”，不能得出“可以达到”。' },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary/70">Goal research case</p>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">案例：每月收益 10% 是否可行？</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            从账户基线、问题和假设开始，沿着当前系统真正具备的研究、验证和模拟能力，一步步得到可审计结论。
          </p>
        </div>
        <Badge variant="destructive" className="h-7 px-3">当前答案：证据不足</Badge>
      </div>

      <Card className="border-amber-200 bg-amber-50/75">
        <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <Landmark className="mt-0.5 size-5 shrink-0 text-amber-800" />
            <div>
              <p className="text-sm font-semibold text-amber-950">IBKR 账户尚未连接</p>
              <p className="mt-1 text-xs leading-5 text-amber-900/75">
                当前机器没有运行 TWS/IB Gateway；示例配置没有真实 DU 账户号；官方 ibapi 依赖也未安装。页面不会编造净值、现金或持仓。
              </p>
            </div>
          </div>
          <Button disabled variant="outline" className="border-amber-300 bg-white/70">读取真实账户</Button>
        </CardContent>
      </Card>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,.95fr)]">
        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2"><Calculator className="size-4" />目标换算器</CardTitle>
                <CardDescription>真实账户未连接时使用明确标记的假设值；连接后由净清算值自动替换。</CardDescription>
              </div>
              <Badge variant="outline">案例假设</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium" htmlFor="account-value">
                假设账户净值（USD）
                <Input id="account-value" type="number" min="0" step="1000" value={accountValue} onChange={(event) => setAccountValue(Number(event.target.value))} />
              </label>
              <label className="space-y-1.5 text-xs font-medium" htmlFor="monthly-target">
                每月复利目标（%）
                <Input id="monthly-target" type="number" min="0" max="100" step="0.5" value={monthlyTarget} onChange={(event) => setMonthlyTarget(Number(event.target.value))} />
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-2">
              {[
                ['每月所需盈利', formatMoney(metrics.monthlyProfit)],
                ['等效年化收益', formatPercent(metrics.annualizedReturn, 1)],
                ['21 日等效日收益', formatPercent(metrics.dailyReturn, 3)],
                ['一年后目标净值', formatMoney(metrics.yearEndValue)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-muted/65 p-3">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="mt-1 text-lg font-semibold tracking-tight">{value}</p>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-xs leading-5 text-orange-950">
              <div className="mb-1 flex items-center gap-2 font-semibold"><AlertTriangle className="size-4" />为什么目标很激进</div>
              每月复利 {formatPercent(monthlyTarget, 1)} 相当于年化 {formatPercent(metrics.annualizedReturn, 1)}。现有风险配置的单日冻结、减仓、清仓阈值分别为 3%、4%、5%；一次 5% 的单日损失就会消耗一半月度目标，需要单独检验这种收益—风险组合是否现实。
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <CardTitle>12 个月复利路径</CardTitle>
            <CardDescription>这是目标轨迹，不是预测，也不是系统对未来收益的承诺。</CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            <Table>
              <TableHeader><TableRow><TableHead className="pl-4">月末</TableHead><TableHead>目标净值</TableHead><TableHead className="pr-4 text-right">累计收益</TableHead></TableRow></TableHeader>
              <TableBody>
                {metrics.months.map((row) => (
                  <TableRow key={row.month}>
                    <TableCell className="pl-4">第 {row.month} 月</TableCell>
                    <TableCell className="font-medium">{formatMoney(row.value)}</TableCell>
                    <TableCell className="pr-4 text-right text-muted-foreground">{formatPercent(accountValue > 0 ? (row.value / accountValue - 1) * 100 : 0, 1)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Target className="size-4" />问题与假设</CardTitle>
            <CardDescription>案例先采用无杠杆、最大回撤不超过 20% 的约束；这不是系统默认替你做出的永久投资选择。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6">
            <div className="rounded-xl border p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">可检验问题</p>
              <p className="mt-2">扣除费用、使用次日开盘执行后，冻结参数的策略能否在独立样本外及至少 63 个交易日模拟观察中，实现几何月均收益不低于 {formatPercent(monthlyTarget, 1)}，同时最大回撤不超过 20%？</p>
            </div>
            <div className="rounded-xl border border-red-200 bg-red-50/65 p-4">
              <p className="text-xs font-semibold text-red-900">H0：不支持</p>
              <p className="mt-1 text-xs text-red-900/75">收益未达到目标、风险超限、样本不足、未跑赢基准或研究协议不合格，任一条件成立都不拒绝 H0。</p>
            </div>
            <div className="rounded-xl border border-teal-200 bg-teal-50/65 p-4">
              <p className="text-xs font-semibold text-teal-900">H1：有条件支持</p>
              <p className="mt-1 text-xs text-teal-900/75">独立样本外达到目标，并通过数据、样本量、回撤、基准、邻参稳健性、walk-forward 和模拟期闸门。</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>当前系统能回答到哪里</CardTitle>
            <CardDescription>账户快照与策略可行性是两类不同证据。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { ok: true, text: '连接就绪后，可读取当前净清算值、当日 P&L、可用资金、超额流动性和持仓。' },
              { ok: true, text: '可完成行情质量检查、探索回测、冻结参数扫描、最终测试和 walk-forward。' },
              { ok: true, text: '可用 GPT Quant 检查研究证据，并进入本地模拟账本和至少 63 日观察。' },
              { ok: false, text: '当前没有 IBKR 历史净值或月收益导入能力；单个账户快照不能证明月度收益。' },
              { ok: false, text: '当前教程结果是合成数据且完整交易为 0，不能用于回答目标是否可行。' },
              { ok: false, text: '当前系统不能承诺未来收益，也不能从目标倒推出应买哪些股票。' },
            ].map(({ ok, text }) => (
              <div key={text} className="flex items-start gap-3 rounded-lg border p-3">
                {ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-teal-700" /> : <Ban className="mt-0.5 size-4 shrink-0 text-red-700" />}
                <p className="text-xs leading-5">{text}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle>从问题到答案：当前案例进度</CardTitle>
          <CardDescription>每一步必须留下输入、输出和状态；被阻塞时不跳过，也不把假设当事实。</CardDescription>
        </CardHeader>
        <CardContent className="divide-y pt-1">
          {steps.map((step, index) => {
            const blocked = step.state === '阻塞';
            const complete = step.state === '完成';
            return (
              <div key={step.title} className="grid gap-3 py-4 sm:grid-cols-[36px_minmax(0,1fr)_auto] sm:items-start">
                <span className={`flex size-8 items-center justify-center rounded-full ${complete ? 'bg-teal-100 text-teal-800' : blocked ? 'bg-red-100 text-red-800' : 'bg-muted text-muted-foreground'}`}>
                  {complete ? <CheckCircle2 className="size-4" /> : blocked ? <LockKeyhole className="size-4" /> : <CircleDashed className="size-4" />}
                </span>
                <div>
                  <p className="text-sm font-semibold">{index + 1}. {step.title}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{step.detail}</p>
                </div>
                <Badge variant={blocked ? 'destructive' : complete ? 'default' : 'outline'}>{step.state}</Badge>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-950 text-slate-100">
        <CardHeader>
          <CardTitle>案例答案</CardTitle>
          <CardDescription className="text-slate-400">基于当前账户连接状态与现有研究证据，而不是基于愿望。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-lg font-semibold leading-7">目前不能得出“每月收益 10% 可实现”。可得出的唯一严谨结论是：目标已被量化，但账户基线和真实研究证据尚未建立，因此结论为 BLOCKED。</p>
          <div className="grid gap-3 text-xs sm:grid-cols-3">
            <div className="rounded-lg bg-white/5 p-3"><p className="text-slate-400">目标强度</p><p className="mt-1 font-semibold">年化 {formatPercent(metrics.annualizedReturn, 1)}</p></div>
            <div className="rounded-lg bg-white/5 p-3"><p className="text-slate-400">第一阻塞项</p><p className="mt-1 font-semibold">IBKR 只读连接未就绪</p></div>
            <div className="rounded-lg bg-white/5 p-3"><p className="text-slate-400">下一项有效工作</p><p className="mt-1 font-semibold">连接 paper TWS 并读取基线</p></div>
          </div>
        </CardContent>
      </Card>

      {expertMode && (
        <div className="grid gap-4 xl:grid-cols-3">
          <CommandBlock>.venv/bin/python scripts/run_live_risk.py --config config/live_risk.paper.yaml --preflight</CommandBlock>
          <CommandBlock>.venv/bin/quant workflow --workspace config/workspace.yaml --strategy momentum --market us --universe baseline --study-file monthly_10pct_001.json --walk-forward</CommandBlock>
          <CommandBlock>PYTHONPATH=../gpt_quant/src .venv/bin/python -m gpt_quant.cli validate-cli-result /absolute/path/to/metrics.json</CommandBlock>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-xl border bg-muted/45 p-4 text-xs leading-5 text-muted-foreground">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        本案例用于研究流程和风险识别，不构成投资建议、收益保证或交易指令。账户快照只描述当前状态，无法单独证明未来或历史月收益。
      </div>
    </div>
  );
}
