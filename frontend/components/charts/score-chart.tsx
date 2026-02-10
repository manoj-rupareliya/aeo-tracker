"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { LLM_COLORS } from "@/lib/utils";

interface ScoreChartProps {
  data: Array<{
    date: string;
    value: number;
    [key: string]: string | number;
  }>;
  showLLMBreakdown?: boolean;
  llmData?: Record<string, number[]>;
}

export function ScoreChart({ data, showLLMBreakdown = false, llmData }: ScoreChartProps) {
  const formatDate = (dateStr: string) => {
    try {
      return format(parseISO(dateStr), "MMM d");
    } catch {
      return dateStr;
    }
  };

  const formatValue = (value: number) => value.toFixed(1);

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis
            domain={[0, 100]}
            stroke="#6b7280"
            fontSize={12}
            tickFormatter={formatValue}
          />
          <Tooltip
            labelFormatter={formatDate}
            formatter={(value: number) => [formatValue(value), "Score"]}
            contentStyle={{
              backgroundColor: "white",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            }}
          />
          {showLLMBreakdown && <Legend />}

          <Line
            type="monotone"
            dataKey="value"
            stroke="#0ea5e9"
            strokeWidth={2}
            dot={{ fill: "#0ea5e9", strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6 }}
            name="Overall Score"
          />

          {showLLMBreakdown && (
            <>
              <Line
                type="monotone"
                dataKey="openai"
                stroke={LLM_COLORS.openai}
                strokeWidth={1.5}
                dot={false}
                name="ChatGPT"
              />
              <Line
                type="monotone"
                dataKey="anthropic"
                stroke={LLM_COLORS.anthropic}
                strokeWidth={1.5}
                dot={false}
                name="Claude"
              />
              <Line
                type="monotone"
                dataKey="google"
                stroke={LLM_COLORS.google}
                strokeWidth={1.5}
                dot={false}
                name="Gemini"
              />
              <Line
                type="monotone"
                dataKey="perplexity"
                stroke={LLM_COLORS.perplexity}
                strokeWidth={1.5}
                dot={false}
                name="Perplexity"
              />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
