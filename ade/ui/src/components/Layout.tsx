import { Link, Outlet } from 'react-router-dom';

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-700 bg-slate-800">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <Link to="/" className="text-lg font-bold text-white no-underline">
            ADE
          </Link>
          <nav className="flex gap-4 text-sm text-slate-400">
            <Link to="/" className="hover:text-white no-underline">
              Projects
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
