'use client';

import { useMemo, useState } from 'react';
import { Check, Clipboard, Search, ShieldAlert, TerminalSquare } from 'lucide-react';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { commandGroups, commands, projectRootCommand, type CommandRisk } from '@/lib/command-catalog';

const riskStyle: Record<CommandRisk, string> = {
  '只读': 'border-teal-200 bg-teal-50 text-teal-800',
  '写入结果': 'border-blue-200 bg-blue-50 text-blue-800',
  '关键确认': 'border-orange-200 bg-orange-50 text-orange-800',
  '高风险维护': 'border-red-200 bg-red-50 text-red-800',
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <Button variant="ghost" size="sm" onClick={copy} aria-label="复制命令">
      {copied ? <Check data-icon="inline-start" /> : <Clipboard data-icon="inline-start" />}
      {copied ? '已复制' : '复制'}
    </Button>
  );
}

export function CommandManual() {
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState('全部');

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return commands.filter((entry) => {
      const matchesGroup = group === '全部' || entry.group === group;
      const matchesQuery = !normalized || [entry.title, entry.purpose, entry.command, entry.group]
        .join(' ')
        .toLowerCase()
        .includes(normalized);
      return matchesGroup && matchesQuery;
    });
  }, [group, query]);

  return (
    <div className="space-y-5">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary/70">Expert reference</p>
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">命令操作手册</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          页面中的每一个动作都应能追溯到这里的一条明确命令。默认从 CLI_research 项目根目录执行。
        </p>
      </div>

      <Card className="border-teal-900/10 bg-teal-50/70">
        <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <TerminalSquare className="mt-0.5 size-5 shrink-0 text-teal-800" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-teal-950">开始前先进入项目目录</p>
              <code className="mt-1 block break-all font-mono text-xs text-teal-900/80">{projectRootCommand}</code>
            </div>
          </div>
          <CopyButton value={projectRootCommand} />
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="relative w-full max-w-xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索命令、用途或参数……"
            className="h-10 pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {['全部', ...commandGroups].map((item) => (
            <Button
              key={item}
              size="sm"
              variant={group === item ? 'default' : 'outline'}
              onClick={() => setGroup(item)}
            >
              {item}
            </Button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle>{filtered.length} 条命令</CardTitle>
          <CardDescription>展开后可查看用途、输出位置、风险说明并复制完整命令。</CardDescription>
        </CardHeader>
        <CardContent>
          <Accordion multiple>
            {filtered.map((entry) => (
              <AccordionItem key={entry.id} value={entry.id}>
                <AccordionTrigger className="gap-4 py-4 hover:no-underline">
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <strong className="text-sm">{entry.title}</strong>
                      <Badge variant="outline" className={riskStyle[entry.risk]}>{entry.risk}</Badge>
                      <Badge variant="secondary">{entry.group}</Badge>
                    </span>
                    <span className="mt-1.5 block text-xs font-normal leading-5 text-muted-foreground">{entry.purpose}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pb-5">
                  <div className="rounded-xl bg-slate-950 p-4 text-slate-100">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-teal-300">Command</span>
                      <CopyButton value={entry.command} />
                    </div>
                    <code className="block break-all font-mono text-xs leading-6">{entry.command}</code>
                  </div>
                  <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                    <div className="rounded-lg bg-muted/60 p-3">
                      <dt className="font-semibold">主要输出</dt>
                      <dd className="mt-1 leading-5 text-muted-foreground">{entry.output}</dd>
                    </div>
                    <div className="rounded-lg bg-muted/60 p-3">
                      <dt className="font-semibold">运行建议</dt>
                      <dd className="mt-1 leading-5 text-muted-foreground">
                        {entry.note ?? (entry.risk === '只读' ? '可安全重复执行，不修改研究状态。' : '运行后检查终端状态和生成文件。')}
                      </dd>
                    </div>
                  </dl>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
          {filtered.length === 0 && (
            <div className="flex flex-col items-center py-14 text-center text-muted-foreground">
              <ShieldAlert className="mb-3 size-7" />
              <p className="text-sm">没有匹配的命令，请换一个关键词。</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
