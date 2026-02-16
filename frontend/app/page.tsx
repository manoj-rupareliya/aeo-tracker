import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <nav className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between items-center">
            <div className="flex items-center">
              <span className="text-2xl font-bold text-primary-600">llmscm</span>
              <span className="text-2xl font-light text-gray-400">.com</span>
            </div>
            <div className="flex items-center gap-4">
              <Link
                href="/auth/login"
                className="text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                Sign in
              </Link>
              <Link href="/auth/register" className="btn-primary">
                Get Started
              </Link>
            </div>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <main>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-24">
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-6xl">
              Know How LLMs
              <span className="text-primary-600"> See Your Brand</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-600 max-w-2xl mx-auto">
              Track brand mentions across ChatGPT, Claude, Gemini, and Perplexity.
              Understand which sources they cite. Measure your visibility over time.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link href="/auth/register" className="btn-primary text-base px-6 py-3">
                Start Free Trial
              </Link>
              <Link
                href="#features"
                className="text-sm font-semibold leading-6 text-gray-900"
              >
                Learn more <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>

          {/* Features */}
          <div id="features" className="mt-32">
            <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
              Everything You Need for GEO Success
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <FeatureCard
                title="Multi-LLM Tracking"
                description="Monitor your brand across ChatGPT, Claude, Gemini, and Perplexity simultaneously."
                icon="📊"
              />
              <FeatureCard
                title="Citation Intelligence"
                description="See which sources LLMs cite when discussing your industry. Identify opportunities."
                icon="🔗"
              />
              <FeatureCard
                title="Competitor Analysis"
                description="Compare your visibility against competitors. Know where you stand."
                icon="🎯"
              />
              <FeatureCard
                title="Visibility Scoring"
                description="Transparent, explainable scores that show exactly why you rank where you do."
                icon="📈"
              />
              <FeatureCard
                title="Time-Series Analytics"
                description="Track changes over time. Measure the impact of your content strategy."
                icon="📉"
              />
              <FeatureCard
                title="Automated Monitoring"
                description="Set it and forget it. Scheduled crawls keep your data fresh."
                icon="⚡"
              />
            </div>
          </div>

          {/* How It Works */}
          <div className="mt-32">
            <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
              How It Works
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <StepCard
                step={1}
                title="Add Your Brand"
                description="Enter your domain, brand names, and competitors"
              />
              <StepCard
                step={2}
                title="Add Keywords"
                description="What topics should LLMs mention your brand for?"
              />
              <StepCard
                step={3}
                title="We Query LLMs"
                description="Automated queries across multiple AI models"
              />
              <StepCard
                step={4}
                title="Get Insights"
                description="Visibility scores, citations, and recommendations"
              />
            </div>
          </div>

          {/* CTA */}
          <div className="mt-32 text-center">
            <div className="bg-primary-600 rounded-2xl py-16 px-8">
              <h2 className="text-3xl font-bold text-white mb-4">
                Ready to Optimize for the AI Era?
              </h2>
              <p className="text-primary-100 mb-8 max-w-2xl mx-auto">
                Join forward-thinking brands already tracking their LLM visibility.
              </p>
              <Link
                href="/auth/register"
                className="inline-flex items-center justify-center rounded-md bg-white px-6 py-3 text-base font-medium text-primary-600 shadow-sm hover:bg-primary-50 transition-colors"
              >
                Get Started Free
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex justify-between items-center">
            <div className="flex items-center">
              <span className="text-xl font-bold text-primary-600">llmscm</span>
              <span className="text-xl font-light text-gray-400">.com</span>
            </div>
            <p className="text-sm text-gray-500">
              LLM Visibility & Citation Intelligence Platform
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: string;
}) {
  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
}

function StepCard({
  step,
  title,
  description,
}: {
  step: number;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center">
      <div className="w-12 h-12 rounded-full bg-primary-600 text-white text-xl font-bold flex items-center justify-center mx-auto mb-4">
        {step}
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
}
