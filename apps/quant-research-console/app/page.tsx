'use client';

import { useState } from 'react';
import {
  Activity,
  BarChart3,
  BookOpenText,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Database,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  Play,
  Radar,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  Target,
  Wrench,
  WalletCards,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { CommandManual } from '@/components/command-manual';
import { GoalCasePage } from '@/components/goal-case-page';
import { DisclosureLabPage } from '@/components/disclosure-lab-page';
import {
  DataPage,
  PaperPage,
  RadarPage,
  ResearchPage,
  ResultsPage,
  RiskPage,
  SpecialtyPage,
} from '@/components/capability-pages';

const navItems = [
  { id: 'workspace', icon: LayoutDashboard, label: '工作台' },
  { id: 'goal-case', icon: Target, label: '目标案例' },
  { id: 'disclosures', icon: FileSearch, label: '申报研究' },
  { id: 'data', icon: Database, label: '数据中心' },
  { id: 'research', icon: FlaskConical, label: '策略研究' },
  { id: 'radar', icon: Radar, label: '每日雷达' },
  { id: 'results', icon: BarChart3, label: '结果中心' },
  { id: 'paper', icon: WalletCards, label: '模拟账户' },
  { id: 'risk', icon: ShieldCheck, label: '风险控制' },
  { id: 'specialty', icon: Wrench, label: '专项分析' },
  { id: 'manual', icon: BookOpenText, label: '操作手册' },
];

const recentRuns = [
  { name: '动量策略 · 美股', type: '合成教程', updated: '昨天 08:27', status: '仅供学习' },
  { name: 'Momentum Volume Radar', type: 'extended 自选池', updated: '等待首次扫描', status: '待运行' },
];

export default function Home() {
  const [expertMode, setExpertMode] = useState(false);
  const [activeSection, setActiveSection] = useState('workspace');
  const command = expertMode
    ? '.venv/bin/quant workflow --workspace config/workspace.yaml --strategy momentum --market us --universe baseline --study-file momentum_001.json --walk-forward'
    : '系统会依次检查数据质量、冻结研究边界、扫描参数并验证结果。';

  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/80 bg-background/92 px-5 backdrop-blur-xl lg:px-7">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Activity className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-[15px] font-semibold tracking-tight">Quant Research Console</h1>
              <Badge variant="secondary" className="hidden sm:inline-flex">本地研究台</Badge>
            </div>
            <p className="text-xs text-muted-foreground">CLI Research × GPT Quant</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 sm:flex">
            <CircleDot className="size-3.5" />
            本地桥接待连接
          </div>
          <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2">
            <TerminalSquare className="size-4 text-muted-foreground" />
            <span className="hidden text-xs font-medium sm:inline">专家模式</span>
            <Switch checked={expertMode} onCheckedChange={setExpertMode} aria-label="切换专家模式" />
          </div>
        </div>
      </header>

      <nav className="sticky top-16 z-20 flex gap-1 overflow-x-auto border-b bg-background/95 px-3 py-2 backdrop-blur lg:hidden" aria-label="移动端导航">
        {navItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveSection(id)}
            className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium ${activeSection === id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
      </nav>

      <div className="mx-auto grid max-w-[1600px] lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden min-h-[calc(100vh-4rem)] border-r bg-sidebar/60 p-4 lg:block">
          <nav className="space-y-1" aria-label="主要导航">
            {navItems.map(({ id, icon: Icon, label }) => (
              <button
                key={label}
                type="button"
                onClick={() => setActiveSection(id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  activeSection === id
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                }`}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </nav>

          <div className="mt-8 rounded-xl border border-teal-900/10 bg-teal-50/80 p-3 text-xs text-teal-950">
            <div className="mb-1 flex items-center gap-2 font-semibold">
              <ShieldCheck className="size-4" />
              安全边界
            </div>
            <p className="leading-5 text-teal-900/75">默认只做研究和模拟，不连接券商、不自动下单。</p>
          </div>
        </aside>

        <section className="min-w-0 p-4 sm:p-6 lg:p-8">
          {activeSection === 'workspace' ? (
          <>
          <div className="mb-7 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary/70">Research workspace</p>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">今天想完成什么研究？</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                从清晰的问题开始，系统会按“数据 → 研究 → 验证 → 模拟观察”的顺序引导你。
              </p>
            </div>
            <Button variant="outline" className="self-start xl:self-auto">
              <RefreshCw data-icon="inline-start" />
              刷新项目状态
            </Button>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]">
            <Card className="border-0 bg-card shadow-[0_12px_40px_rgb(15_35_42/7%)] ring-border">
              <CardHeader className="border-b">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle className="text-lg">开始一次正式策略研究</CardTitle>
                    <CardDescription className="mt-1">适合验证一个已经写清楚规则的策略假设</CardDescription>
                  </div>
                  <Badge className="bg-teal-700 text-white">推荐流程</Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-1">
                <div className="divide-y">
                  {[
                    ['1', '确认数据状态', '检查美股 baseline 股票池的覆盖、缺口与更新时间', '数据检查'],
                    ['2', '设置研究边界', '选择策略、时间范围和训练/验证/最终测试比例', '研究配置'],
                    ['3', '预览并冻结实验', '先预览日期边界，确认后才允许消耗最终测试', '关键确认'],
                    ['4', '阅读验证结论', '将结果交给 GPT Quant 闸门，区分支持、反证与缺口', '结果解释'],
                  ].map(([number, title, description, tag]) => (
                    <button type="button" key={number} className="group flex w-full items-center gap-4 py-4 text-left">
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary font-mono text-xs font-semibold text-secondary-foreground group-hover:bg-primary group-hover:text-primary-foreground">
                        {number}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm font-semibold">{title}</strong>
                          <Badge variant="outline" className="font-normal">{tag}</Badge>
                        </span>
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
                      </span>
                      <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
                <div className="mt-2 flex flex-col gap-3 rounded-xl bg-slate-950 p-4 text-slate-100 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-teal-300">
                      {expertMode ? '将要执行的命令' : '系统将做什么'}
                    </p>
                    <code className={`block text-xs leading-5 ${expertMode ? 'break-all font-mono' : 'font-sans text-slate-300'}`}>
                      {command}
                    </code>
                  </div>
                  <Button disabled className="bg-teal-400 text-slate-950 hover:bg-teal-300">
                    <Play data-icon="inline-start" />
                    连接后运行
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
              <Card className="border-0 bg-[#0d2e34] text-white shadow-[0_12px_40px_rgb(15_35_42/10%)] ring-0">
                <CardHeader>
                  <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-white/10">
                    <Radar className="size-5 text-teal-300" />
                  </div>
                  <CardTitle>每日美股雷达</CardTitle>
                  <CardDescription className="text-teal-50/65">扫描固定自选池，查看量价动量与突破信号</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button variant="secondary" className="w-full bg-white text-slate-950 hover:bg-teal-50">
                    打开雷达
                    <ChevronRight data-icon="inline-end" />
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-orange-50 text-orange-700">
                    <ShieldCheck className="size-5" />
                  </div>
                  <CardTitle>验证已有结果</CardTitle>
                  <CardDescription>选择一个 metrics.json，检查是否具备进入模拟观察的证据。</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button variant="outline" className="w-full">选择研究结果</Button>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card className="mt-5">
            <CardHeader className="border-b">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle>最近项目</CardTitle>
                  <CardDescription>研究结果、雷达扫描和模拟状态都会集中在这里</CardDescription>
                </div>
                <Button variant="ghost" size="sm">查看全部</Button>
              </div>
            </CardHeader>
            <CardContent className="px-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-4">名称</TableHead>
                    <TableHead>数据范围</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead className="pr-4 text-right">状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentRuns.map((run) => (
                    <TableRow key={run.name}>
                      <TableCell className="pl-4 font-medium">{run.name}</TableCell>
                      <TableCell className="text-muted-foreground">{run.type}</TableCell>
                      <TableCell className="text-muted-foreground">{run.updated}</TableCell>
                      <TableCell className="pr-4 text-right">
                        <Badge variant={run.status === '仅供学习' ? 'destructive' : 'outline'}>{run.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="mt-5 flex items-start gap-3 rounded-xl border border-teal-900/10 bg-teal-50 p-4 text-sm text-teal-950 lg:hidden">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            <p>系统默认只进行研究与模拟，不连接券商、不自动下单。</p>
          </div>
          </>
          ) : activeSection === 'data' ? (
            <DataPage expertMode={expertMode} />
          ) : activeSection === 'goal-case' ? (
            <GoalCasePage expertMode={expertMode} />
          ) : activeSection === 'disclosures' ? (
            <DisclosureLabPage expertMode={expertMode} />
          ) : activeSection === 'research' ? (
            <ResearchPage expertMode={expertMode} />
          ) : activeSection === 'radar' ? (
            <RadarPage expertMode={expertMode} />
          ) : activeSection === 'results' ? (
            <ResultsPage expertMode={expertMode} />
          ) : activeSection === 'paper' ? (
            <PaperPage expertMode={expertMode} />
          ) : activeSection === 'risk' ? (
            <RiskPage expertMode={expertMode} />
          ) : activeSection === 'specialty' ? (
            <SpecialtyPage expertMode={expertMode} />
          ) : (
            <CommandManual />
          )}
        </section>
      </div>
    </main>
  );
}
