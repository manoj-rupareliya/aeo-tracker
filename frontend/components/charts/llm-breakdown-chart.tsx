"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { LLM_COLORS, LLM_DISPLAY_NAMES } from "@/lib/utils";

interface LLMBreakdownChartProps {
  data: Array<{
    provider: string;
    avg_score: number;
    mention_rate?: number;
    citation_rate?: number;
  }>;
}

export function LLMBreakdownChart({ data }: LLMBreakdownChartProps) {
  const chartData = data.map((item) => ({
    name: LLM_DISPLAY_NAMES[item.provider] || item.provider,
    score: item.avg_score,
    provider: item.provider,
  }));

  return (
    <div className="h-[250px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          layout="vertical"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            type="number"
            domain={[0, 100]}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis
            dataKey="name"
            type="category"
            stroke="#6b7280"
            fontSize={12}
            width={100}
          />
          <Tooltip
            formatter={(value: number) => [value.toFixed(1), "Score"]}
            contentStyle={{
              backgroundColor: "white",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            }}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={LLM_COLORS[entry.provider] || "#6b7280"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
