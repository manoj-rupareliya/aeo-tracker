"""
Admin Dashboard Routes
Web-based admin interface with HTML templates
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, Project, Keyword, LLMRun, LLMRunStatus, UserAPIKey
from app.utils import get_db, hash_password
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# Simple session-based auth for admin (in production, use proper auth)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Change this in production!
admin_sessions = set()


def get_base_template(title: str, content: str, active_page: str = "") -> str:
    """Generate base HTML template with navigation"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - llmscm Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        primary: {{
                            50: '#f5f3ff',
                            100: '#ede9fe',
                            200: '#ddd6fe',
                            300: '#c4b5fd',
                            400: '#a78bfa',
                            500: '#8b5cf6',
                            600: '#7c3aed',
                            700: '#6d28d9',
                            800: '#5b21b6',
                            900: '#4c1d95',
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .gradient-bg {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="flex">
        <!-- Sidebar -->
        <aside class="w-64 bg-gray-900 min-h-screen fixed">
            <div class="p-6">
                <h1 class="text-2xl font-bold text-white">llmscm</h1>
                <p class="text-gray-400 text-sm">Admin Dashboard</p>
            </div>
            <nav class="mt-6">
                <a href="/admin/" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'dashboard' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                    </svg>
                    Dashboard
                </a>
                <a href="/admin/users" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'users' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
                    </svg>
                    Users
                </a>
                <a href="/admin/projects" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'projects' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                    </svg>
                    Projects
                </a>
                <a href="/admin/llm-runs" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'llm-runs' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                    LLM Runs
                </a>
                <a href="/admin/api-keys" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'api-keys' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                    </svg>
                    API Keys
                </a>
                <a href="/admin/settings" class="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white {'bg-gray-800 text-white' if active_page == 'settings' else ''}">
                    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    Settings
                </a>
                <div class="border-t border-gray-700 mt-6 pt-6">
                    <a href="/admin/logout" class="flex items-center px-6 py-3 text-red-400 hover:bg-gray-800 hover:text-red-300">
                        <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                        </svg>
                        Logout
                    </a>
                </div>
            </nav>
        </aside>

        <!-- Main Content -->
        <main class="ml-64 flex-1 p-8">
            {content}
        </main>
    </div>
</body>
</html>
"""


def check_admin_auth(request: Request) -> bool:
    """Check if request has valid admin session"""
    session_id = request.cookies.get("admin_session")
    return session_id in admin_sessions


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """Admin login page"""
    error_html = f'<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">{error}</div>' if error else ""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - llmscm</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-violet-600 to-indigo-700 min-h-screen flex items-center justify-center">
    <div class="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold text-gray-900">llmscm Admin</h1>
            <p class="text-gray-500 mt-2">Sign in to access the dashboard</p>
        </div>
        {error_html}
        <form method="POST" action="/admin/login" class="space-y-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input type="text" name="username" required
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                    placeholder="admin">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input type="password" name="password" required
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                    placeholder="Enter password">
            </div>
            <button type="submit"
                class="w-full bg-gradient-to-r from-violet-600 to-indigo-600 text-white py-3 rounded-lg font-medium hover:from-violet-500 hover:to-indigo-500 transition-all">
                Sign In
            </button>
        </form>
        <p class="text-center text-gray-500 text-sm mt-6">
            Default: admin / admin123
        </p>
    </div>
</body>
</html>
"""


@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process admin login"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        import secrets
        session_id = secrets.token_hex(32)
        admin_sessions.add(session_id)
        response = RedirectResponse(url="/admin/", status_code=303)
        response.set_cookie("admin_session", session_id, httponly=True, max_age=86400)
        return response
    return RedirectResponse(url="/admin/login?error=Invalid credentials", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Admin logout"""
    session_id = request.cookies.get("admin_session")
    if session_id in admin_sessions:
        admin_sessions.discard(session_id)
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin dashboard home"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    # Get stats
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    project_count = (await db.execute(select(func.count(Project.id)))).scalar()
    keyword_count = (await db.execute(select(func.count(Keyword.id)))).scalar()

    # LLM run stats
    total_runs = (await db.execute(select(func.count(LLMRun.id)))).scalar()
    completed_runs = (await db.execute(
        select(func.count(LLMRun.id)).where(LLMRun.status == LLMRunStatus.COMPLETED)
    )).scalar()
    failed_runs = (await db.execute(
        select(func.count(LLMRun.id)).where(LLMRun.status == LLMRunStatus.FAILED)
    )).scalar()

    # Recent users
    recent_users_result = await db.execute(
        select(User).order_by(desc(User.created_at)).limit(5)
    )
    recent_users = recent_users_result.scalars().all()

    recent_users_html = ""
    for user in recent_users:
        recent_users_html += f"""
        <tr class="border-b">
            <td class="py-3 px-4">{user.email}</td>
            <td class="py-3 px-4">{user.full_name}</td>
            <td class="py-3 px-4">
                <span class="px-2 py-1 text-xs rounded-full {'bg-green-100 text-green-700' if user.is_active else 'bg-red-100 text-red-700'}">
                    {'Active' if user.is_active else 'Inactive'}
                </span>
            </td>
            <td class="py-3 px-4 text-gray-500">{user.created_at.strftime('%Y-%m-%d %H:%M')}</td>
        </tr>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Dashboard</h2>
        <p class="text-gray-500">Welcome to the llmscm admin panel</p>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-gray-500 text-sm">Total Users</p>
                    <p class="text-3xl font-bold text-gray-900">{user_count}</p>
                </div>
                <div class="w-12 h-12 bg-violet-100 rounded-xl flex items-center justify-center">
                    <svg class="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
                    </svg>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-gray-500 text-sm">Total Projects</p>
                    <p class="text-3xl font-bold text-gray-900">{project_count}</p>
                </div>
                <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                    <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                    </svg>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-gray-500 text-sm">Total Keywords</p>
                    <p class="text-3xl font-bold text-gray-900">{keyword_count}</p>
                </div>
                <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                    <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                    </svg>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-gray-500 text-sm">LLM Runs</p>
                    <p class="text-3xl font-bold text-gray-900">{total_runs}</p>
                    <p class="text-xs text-gray-400">{completed_runs} completed, {failed_runs} failed</p>
                </div>
                <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
                    <svg class="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                </div>
            </div>
        </div>
    </div>

    <!-- Recent Users -->
    <div class="bg-white rounded-xl shadow-sm">
        <div class="p-6 border-b">
            <h3 class="text-lg font-semibold text-gray-900">Recent Users</h3>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Email</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Name</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Status</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Created</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_users_html if recent_users_html else '<tr><td colspan="4" class="py-8 text-center text-gray-500">No users yet</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """

    return get_base_template("Dashboard", content, "dashboard")


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: AsyncSession = Depends(get_db), page: int = 1):
    """User management page"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    page_size = 20
    offset = (page - 1) * page_size

    # Get users
    result = await db.execute(
        select(User).order_by(desc(User.created_at)).offset(offset).limit(page_size)
    )
    users = result.scalars().all()

    total_count = (await db.execute(select(func.count(User.id)))).scalar()
    total_pages = (total_count + page_size - 1) // page_size

    users_html = ""
    for user in users:
        users_html += f"""
        <tr class="border-b hover:bg-gray-50">
            <td class="py-4 px-4">
                <div class="flex items-center">
                    <div class="w-10 h-10 bg-violet-100 rounded-full flex items-center justify-center mr-3">
                        <span class="text-violet-600 font-medium">{user.full_name[0].upper() if user.full_name else 'U'}</span>
                    </div>
                    <div>
                        <p class="font-medium text-gray-900">{user.full_name}</p>
                        <p class="text-sm text-gray-500">{user.email}</p>
                    </div>
                </div>
            </td>
            <td class="py-4 px-4">
                <span class="px-3 py-1 text-xs font-medium rounded-full bg-violet-100 text-violet-700">
                    {user.subscription_tier.value if user.subscription_tier else 'free'}
                </span>
            </td>
            <td class="py-4 px-4">
                <span class="px-3 py-1 text-xs font-medium rounded-full {'bg-green-100 text-green-700' if user.is_active else 'bg-red-100 text-red-700'}">
                    {'Active' if user.is_active else 'Inactive'}
                </span>
            </td>
            <td class="py-4 px-4 text-gray-500">
                {user.tokens_used_this_month:,} / {user.monthly_token_limit:,}
            </td>
            <td class="py-4 px-4 text-gray-500">
                {user.last_login_at.strftime('%Y-%m-%d %H:%M') if user.last_login_at else 'Never'}
            </td>
            <td class="py-4 px-4 text-gray-500">
                {user.created_at.strftime('%Y-%m-%d')}
            </td>
            <td class="py-4 px-4">
                <div class="flex gap-2">
                    <a href="/admin/users/{user.id}" class="text-blue-600 hover:text-blue-800">View</a>
                    <a href="/admin/users/{user.id}/toggle" class="text-{'red' if user.is_active else 'green'}-600 hover:text-{'red' if user.is_active else 'green'}-800">
                        {'Disable' if user.is_active else 'Enable'}
                    </a>
                </div>
            </td>
        </tr>
        """

    # Pagination
    pagination_html = ""
    if total_pages > 1:
        pagination_html = '<div class="flex justify-center gap-2 p-4">'
        for p in range(1, total_pages + 1):
            active = "bg-violet-600 text-white" if p == page else "bg-gray-100 text-gray-700 hover:bg-gray-200"
            pagination_html += f'<a href="/admin/users?page={p}" class="px-4 py-2 rounded-lg {active}">{p}</a>'
        pagination_html += '</div>'

    content = f"""
    <div class="flex items-center justify-between mb-8">
        <div>
            <h2 class="text-3xl font-bold text-gray-900">Users</h2>
            <p class="text-gray-500">Manage user accounts</p>
        </div>
        <a href="/admin/users/new" class="bg-violet-600 text-white px-4 py-2 rounded-lg hover:bg-violet-700 transition-colors">
            + Add User
        </a>
    </div>

    <div class="bg-white rounded-xl shadow-sm">
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">User</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Plan</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Status</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Tokens</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Last Login</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Created</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {users_html if users_html else '<tr><td colspan="7" class="py-8 text-center text-gray-500">No users found</td></tr>'}
                </tbody>
            </table>
        </div>
        {pagination_html}
    </div>
    """

    return get_base_template("Users", content, "users")


@router.get("/users/new", response_class=HTMLResponse)
async def new_user_page(request: Request):
    """Create new user form"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    content = """
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Create User</h2>
        <p class="text-gray-500">Add a new user account</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-6 max-w-xl">
        <form method="POST" action="/admin/users/new" class="space-y-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                <input type="email" name="email" required
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
                <input type="text" name="full_name" required
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Password *</label>
                <input type="password" name="password" required minlength="8"
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Subscription Tier</label>
                <select name="subscription_tier"
                    class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent">
                    <option value="free">Free</option>
                    <option value="starter">Starter</option>
                    <option value="professional">Professional</option>
                    <option value="enterprise">Enterprise</option>
                </select>
            </div>
            <div class="flex gap-4">
                <button type="submit" class="bg-violet-600 text-white px-6 py-3 rounded-lg hover:bg-violet-700 transition-colors">
                    Create User
                </button>
                <a href="/admin/users" class="bg-gray-100 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-200 transition-colors">
                    Cancel
                </a>
            </div>
        </form>
    </div>
    """

    return get_base_template("Create User", content, "users")


@router.post("/users/new")
async def create_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    subscription_tier: str = Form("free"),
):
    """Create new user"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    from app.models import SubscriptionTier

    # Check if email exists
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return RedirectResponse(url="/admin/users/new?error=Email already exists", status_code=303)

    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        subscription_tier=SubscriptionTier(subscription_tier),
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()

    return RedirectResponse(url="/admin/users?success=User created", status_code=303)


@router.get("/users/{user_id}/toggle")
async def toggle_user_status(request: Request, user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Toggle user active status"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user:
        user.is_active = not user.is_active
        await db.commit()

    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: AsyncSession = Depends(get_db), page: int = 1):
    """Projects management page"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    page_size = 20
    offset = (page - 1) * page_size

    result = await db.execute(
        select(Project)
        .options(selectinload(Project.owner))
        .order_by(desc(Project.created_at))
        .offset(offset)
        .limit(page_size)
    )
    projects = result.scalars().all()

    projects_html = ""
    for project in projects:
        # Get keyword count
        kw_count = (await db.execute(
            select(func.count(Keyword.id)).where(Keyword.project_id == project.id)
        )).scalar()

        projects_html += f"""
        <tr class="border-b hover:bg-gray-50">
            <td class="py-4 px-4">
                <div>
                    <p class="font-medium text-gray-900">{project.name}</p>
                    <p class="text-sm text-gray-500">{project.domain}</p>
                </div>
            </td>
            <td class="py-4 px-4 text-gray-600">{project.owner.email if project.owner else 'N/A'}</td>
            <td class="py-4 px-4">
                <span class="px-3 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700">
                    {project.industry.value if project.industry else 'other'}
                </span>
            </td>
            <td class="py-4 px-4 text-gray-600">{kw_count}</td>
            <td class="py-4 px-4">
                <span class="px-3 py-1 text-xs font-medium rounded-full {'bg-green-100 text-green-700' if project.is_active else 'bg-red-100 text-red-700'}">
                    {'Active' if project.is_active else 'Inactive'}
                </span>
            </td>
            <td class="py-4 px-4 text-gray-500">{project.created_at.strftime('%Y-%m-%d')}</td>
            <td class="py-4 px-4">
                <a href="/admin/projects/{project.id}" class="text-blue-600 hover:text-blue-800">View</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Projects</h2>
        <p class="text-gray-500">View and manage all projects</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm">
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Project</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Owner</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Industry</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Keywords</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Status</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Created</th>
                        <th class="text-left py-4 px-4 text-gray-600 font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {projects_html if projects_html else '<tr><td colspan="7" class="py-8 text-center text-gray-500">No projects found</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """

    return get_base_template("Projects", content, "projects")


@router.get("/llm-runs", response_class=HTMLResponse)
async def llm_runs_page(request: Request, db: AsyncSession = Depends(get_db), page: int = 1, status_filter: str = ""):
    """LLM Runs monitoring page"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    page_size = 50
    offset = (page - 1) * page_size

    query = select(LLMRun).order_by(desc(LLMRun.created_at))
    if status_filter:
        query = query.where(LLMRun.status == status_filter)

    result = await db.execute(query.offset(offset).limit(page_size))
    runs = result.scalars().all()

    # Get status counts
    status_counts = {}
    for s in LLMRunStatus:
        count = (await db.execute(
            select(func.count(LLMRun.id)).where(LLMRun.status == s)
        )).scalar()
        status_counts[s.value] = count

    runs_html = ""
    for run in runs:
        status_color = {
            "pending": "bg-yellow-100 text-yellow-700",
            "processing": "bg-blue-100 text-blue-700",
            "executing": "bg-blue-100 text-blue-700",
            "completed": "bg-green-100 text-green-700",
            "failed": "bg-red-100 text-red-700",
            "cached": "bg-purple-100 text-purple-700",
        }.get(run.status.value, "bg-gray-100 text-gray-700")

        runs_html += f"""
        <tr class="border-b hover:bg-gray-50">
            <td class="py-3 px-4 text-sm text-gray-500">{str(run.id)[:8]}...</td>
            <td class="py-3 px-4">{run.provider.value}</td>
            <td class="py-3 px-4 text-sm">{run.model_name or 'N/A'}</td>
            <td class="py-3 px-4">
                <span class="px-2 py-1 text-xs font-medium rounded-full {status_color}">
                    {run.status.value}
                </span>
            </td>
            <td class="py-3 px-4 text-sm text-gray-500">{run.input_tokens or 0} / {run.output_tokens or 0}</td>
            <td class="py-3 px-4 text-sm text-gray-500">${run.estimated_cost_usd:.4f if run.estimated_cost_usd else '0.0000'}</td>
            <td class="py-3 px-4 text-sm text-gray-500">{run.created_at.strftime('%Y-%m-%d %H:%M')}</td>
            <td class="py-3 px-4 text-sm text-red-500">{run.error_message[:30] + '...' if run.error_message and len(run.error_message) > 30 else run.error_message or ''}</td>
        </tr>
        """

    # Status filter buttons
    status_buttons = ""
    for s, count in status_counts.items():
        active = "bg-violet-600 text-white" if status_filter == s else "bg-gray-100 text-gray-700 hover:bg-gray-200"
        status_buttons += f'<a href="/admin/llm-runs?status_filter={s}" class="px-4 py-2 rounded-lg {active}">{s} ({count})</a>'

    content = f"""
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">LLM Runs</h2>
        <p class="text-gray-500">Monitor LLM execution status</p>
    </div>

    <div class="flex gap-2 mb-6 flex-wrap">
        <a href="/admin/llm-runs" class="px-4 py-2 rounded-lg {'bg-violet-600 text-white' if not status_filter else 'bg-gray-100 text-gray-700 hover:bg-gray-200'}">All ({sum(status_counts.values())})</a>
        {status_buttons}
    </div>

    <div class="bg-white rounded-xl shadow-sm">
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">ID</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Provider</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Model</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Status</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Tokens</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Cost</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Created</th>
                        <th class="text-left py-3 px-4 text-gray-600 font-medium">Error</th>
                    </tr>
                </thead>
                <tbody>
                    {runs_html if runs_html else '<tr><td colspan="8" class="py-8 text-center text-gray-500">No LLM runs found</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """

    return get_base_template("LLM Runs", content, "llm-runs")


@router.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request, db: AsyncSession = Depends(get_db)):
    """API Keys configuration page"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    # Check which API keys are configured
    api_keys_status = {
        "OpenAI": bool(settings.OPENAI_API_KEY),
        "Anthropic": bool(settings.ANTHROPIC_API_KEY),
        "Google": bool(settings.GOOGLE_API_KEY),
        "Perplexity": bool(settings.PERPLEXITY_API_KEY),
    }

    keys_html = ""
    for provider, configured in api_keys_status.items():
        status_class = "bg-green-100 text-green-700" if configured else "bg-red-100 text-red-700"
        status_text = "Configured" if configured else "Not Configured"

        keys_html += f"""
        <div class="bg-white rounded-xl shadow-sm p-6 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center">
                    <span class="text-xl font-bold text-gray-600">{provider[0]}</span>
                </div>
                <div>
                    <p class="font-medium text-gray-900">{provider}</p>
                    <p class="text-sm text-gray-500">LLM Provider API Key</p>
                </div>
            </div>
            <span class="px-4 py-2 text-sm font-medium rounded-full {status_class}">{status_text}</span>
        </div>
        """

    content = f"""
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">API Keys</h2>
        <p class="text-gray-500">Platform-level LLM provider API keys</p>
    </div>

    <div class="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6">
        <p class="text-yellow-800">
            <strong>Note:</strong> API keys are configured in the backend <code>.env</code> file.
            Edit the file and restart the server to update keys.
        </p>
    </div>

    <div class="grid gap-4">
        {keys_html}
    </div>

    <div class="mt-8 bg-white rounded-xl shadow-sm p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Environment Variables</h3>
        <pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_API_KEY=your-key-here
PERPLEXITY_API_KEY=pplx-your-key-here
        </pre>
    </div>
    """

    return get_base_template("API Keys", content, "api-keys")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """System settings page"""
    if not check_admin_auth(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    content = f"""
    <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Settings</h2>
        <p class="text-gray-500">System configuration</p>
    </div>

    <div class="grid gap-6">
        <div class="bg-white rounded-xl shadow-sm p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Application</h3>
            <div class="space-y-4">
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Environment</span>
                    <span class="font-medium">{settings.APP_ENV}</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Debug Mode</span>
                    <span class="font-medium">{'Enabled' if settings.DEBUG else 'Disabled'}</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">API Version</span>
                    <span class="font-medium">{settings.API_VERSION}</span>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">LLM Configuration</h3>
            <div class="space-y-4">
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Default Temperature</span>
                    <span class="font-medium">{settings.LLM_DEFAULT_TEMPERATURE}</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Max Tokens</span>
                    <span class="font-medium">{settings.LLM_DEFAULT_MAX_TOKENS}</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Request Timeout</span>
                    <span class="font-medium">{settings.LLM_REQUEST_TIMEOUT}s</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Max Retries</span>
                    <span class="font-medium">{settings.LLM_MAX_RETRIES}</span>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Rate Limits</h3>
            <div class="space-y-4">
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Requests per Minute</span>
                    <span class="font-medium">{settings.RATE_LIMIT_REQUESTS_PER_MINUTE}</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">LLM Calls per Minute</span>
                    <span class="font-medium">{settings.RATE_LIMIT_LLM_CALLS_PER_MINUTE}</span>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Cache</h3>
            <div class="space-y-4">
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Cache TTL</span>
                    <span class="font-medium">{settings.REDIS_CACHE_TTL // 86400} days</span>
                </div>
                <div class="flex justify-between py-2 border-b">
                    <span class="text-gray-600">Redis URL</span>
                    <span class="font-medium text-sm">{settings.REDIS_URL[:30]}...</span>
                </div>
            </div>
        </div>
    </div>
    """

    return get_base_template("Settings", content, "settings")
