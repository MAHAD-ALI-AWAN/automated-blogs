let allPosts = [];
let currentCategory = 'All';
let searchQuery = '';
let currentPage = 1;
let showSavedOnly = false;
const postsPerPage = 6;
const GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/MAHAD-ALI-AWAN/automated-blogs/main';

function initHeaderWidgets() {
    const greetingEl = document.getElementById('dynamic-greeting');
    const dateEl = document.getElementById('live-date-badge');
    
    if (greetingEl) {
        const hour = new Date().getHours();
        let greet = "Welcome";
        if (hour < 12) greet = "🌅 Good Morning";
        else if (hour < 17) greet = "☀️ Good Afternoon";
        else greet = "🌙 Good Evening";
        greetingEl.textContent = greet;
    }

    if (dateEl) {
        const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };
        dateEl.textContent = `📅 ${new Date().toLocaleDateString('en-US', options)}`;
    }
}

function showFeedLoader() {
    const container = document.getElementById('posts-container');
    if (!container) return;

    container.innerHTML = `
        <div class="feed-loader" aria-live="polite">
            <div class="feed-loader-card">
                <div>
                    <div class="feed-loader-line short"></div>
                    <div class="feed-loader-line long"></div>
                    <div class="feed-loader-line medium"></div>
                </div>
            </div>
            <div class="feed-loader-card">
                <div>
                    <div class="feed-loader-line short"></div>
                    <div class="feed-loader-line long"></div>
                    <div class="feed-loader-line medium"></div>
                </div>
            </div>
        </div>
    `;
}

function isPostHot(post) {
    if (!post.is_hot || !post.date) return false;
    const postDate = new Date(post.date);
    const now = new Date();
    const diffInHours = (now - postDate) / (1000 * 60 * 60);
    return diffInHours <= 24;
}

// LocalStorage Bookmarks Management
function getSavedPosts() {
    try {
        return JSON.parse(localStorage.getItem('byte_pulse_saved') || '[]');
    } catch {
        return [];
    }
}

function toggleBookmark(event, file) {
    event.stopPropagation();
    let saved = getSavedPosts();
    if (saved.includes(file)) {
        saved = saved.filter(f => f !== file);
        showToast("Removed from saved bookmarks");
    } else {
        saved.push(file);
        showToast("Article bookmarked successfully! 🔖");
    }
    localStorage.setItem('byte_pulse_saved', JSON.stringify(saved));
    updateSavedCount();
    renderPosts();
}

function updateSavedCount() {
    const countEl = document.getElementById('saved-count');
    if (countEl) {
        countEl.textContent = getSavedPosts().length;
    }
}

// Modern Toast Notification (Top-Right)
function showToast(message) {
    const toast = document.getElementById('toast-notification');
    const msgEl = document.getElementById('toast-message');
    if (!toast || !msgEl) return;

    msgEl.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Quick Share Function with Toast
function shareArticle(event, title, file) {
    event.stopPropagation();
    const shareUrl = window.location.origin + '/post.html?file=' + encodeURIComponent(file);
    if (navigator.clipboard) {
        navigator.clipboard.writeText(shareUrl).then(() => {
            showToast("Link copied to clipboard! 🔗");
        }).catch(() => {
            showToast("Unable to copy link.");
        });
    } else {
        showToast("Clipboard not supported.");
    }
}

// Surprise Me (Random Article)
function surpriseMe() {
    if (allPosts.length === 0) return;
    const randomPost = allPosts[Math.floor(Math.random() * allPosts.length)];
    showToast(`🎲 Opening random article: ${randomPost.title.substring(0, 30)}...`);
    setTimeout(() => {
        window.location.href = `post.html?file=${encodeURIComponent(randomPost.file)}`;
    }, 1000);
}

// Copy RSS Feed Link
function copyRssFeed() {
    const rssUrl = `${GITHUB_RAW_BASE}/frontend/posts.json`;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(rssUrl).then(() => {
            showToast("📡 RSS JSON feed link copied!");
        });
    } else {
        showToast("Unable to copy RSS link.");
    }
}

async function fetchPosts() {
    initHeaderWidgets();
    const container = document.getElementById('posts-container');
    showFeedLoader();
    
    try {
        const response = await fetch(`${GITHUB_RAW_BASE}/frontend/posts.json`);
        if (!response.ok) throw new Error("Posts index not found.");
        
        allPosts = await response.json();

        if (allPosts.length === 0) {
            container.innerHTML = `<p class="text-slate-500 py-10 text-center">No articles available yet. Please run pipeline.py!</p>`;
            return;
        }

        updateSavedCount();
        renderStatsBar();
        renderCategories();
        renderPosts();

    } catch (e) {
        container.innerHTML = `<p class="text-slate-500 py-10 text-center">No articles available yet. Please run pipeline.py!</p>`;
    }
}

function renderStatsBar() {
    const statsEl = document.getElementById('stats-bar');
    if (!statsEl) return;
    
    const total = allPosts.length;
    const hotCount = allPosts.filter(p => isPostHot(p)).length;
    const genres = new Set(allPosts.map(p => p.category || 'General')).size;

    statsEl.innerHTML = `
        <span>📝 <b>${total}</b> Posts</span>
        <span class="text-slate-600">•</span>
        <span>🔥 <b>${hotCount}</b> Hot</span>
        <span class="text-slate-600">•</span>
        <span>📂 <b>${genres}</b> Genres</span>
    `;
}

// Render Categories with Article Counts
function renderCategories() {
    const select = document.getElementById('category-select');
    const hotBtn = document.getElementById('hot-tab-btn');
    const savedBtn = document.getElementById('saved-tab-btn');
    if (!select) return;
    
    const categories = ['All', ...new Set(allPosts.map(p => p.category || 'General'))];
    
    select.innerHTML = categories.map(cat => {
        let count = allPosts.length;
        if (cat !== 'All') {
            count = allPosts.filter(p => (p.category || 'General') === cat).length;
        }
        const label = cat === 'All' ? `📂 All Categories (${allPosts.length})` : `${cat} (${count})`;
        return `
            <option value="${cat.replace(/'/g, "\\'")}" ${currentCategory === cat && !showSavedOnly ? 'selected' : ''} class="bg-slate-900 text-slate-100 py-2">
                ${label}
            </option>
        `;
    }).join('');

    if (hotBtn) {
        if (currentCategory === '🔥 Hot Topics' && !showSavedOnly) {
            hotBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-amber-500 text-slate-950 border-amber-400 flex items-center justify-center gap-1.5 shrink-0 shadow-lg shadow-amber-500/20";
        } else {
            hotBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20 flex items-center justify-center gap-1.5 shrink-0";
        }
    }

    if (savedBtn) {
        if (showSavedOnly) {
            savedBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-blue-500 text-slate-950 border-blue-400 flex items-center justify-center gap-1.5 shrink-0 shadow-lg shadow-blue-500/20";
        } else {
            savedBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-blue-500/10 text-blue-400 border-blue-500/30 hover:bg-blue-500/20 flex items-center justify-center gap-1.5 shrink-0";
        }
    }
}

function filterCategory(category) {
    showSavedOnly = false;
    currentCategory = category;
    currentPage = 1;
    renderCategories();
    renderPosts();
}

function toggleSavedFilter() {
    showSavedOnly = !showSavedOnly;
    currentPage = 1;
    renderCategories();
    renderPosts();
}

function toggleHotFilter() {
    showSavedOnly = false;
    if (currentCategory === '🔥 Hot Topics') {
        currentCategory = 'All';
    } else {
        currentCategory = '🔥 Hot Topics';
    }
    currentPage = 1;
    renderCategories();
    renderPosts();
}

document.addEventListener('DOMContentLoaded', () => {
    const hotBtn = document.getElementById('hot-tab-btn');
    if (hotBtn) {
        hotBtn.onclick = (e) => {
            e.preventDefault();
            toggleHotFilter();
        };
    }
});

function handleSearch(query) {
    searchQuery = query.toLowerCase().trim();
    currentPage = 1;
    renderPosts();
}

function changePage(direction) {
    currentPage += direction;
    renderPosts();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderPosts() {
    const container = document.getElementById('posts-container');
    if (!container) return;
    
    let html = '';
    const savedFiles = getSavedPosts();

    // Saved Bookmarks View
    if (showSavedOnly) {
        let filteredPosts = allPosts.filter(p => savedFiles.includes(p.file));
        if (searchQuery) {
            filteredPosts = filteredPosts.filter(p => p.title.toLowerCase().includes(searchQuery));
        }

        if (filteredPosts.length === 0) {
            container.innerHTML = `<div class="py-16 text-center bg-slate-900/40 rounded-2xl border border-slate-800/80"><p class="text-slate-400 text-sm">You have not bookmarked any articles yet.</p></div>`;
            return;
        }

        html += `<div class="mb-6 flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider">
                    <span>🔖 Your Saved Bookmarks</span>
                    <div class="flex-1 border-t border-blue-500/20"></div>
                 </div>`;

        html += `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">`;
        html += filteredPosts.map(post => {
            const isSaved = savedFiles.includes(post.file);
            const hotStatus = isPostHot(post);
            return createCardHtml(post, hotStatus, isSaved);
        }).join('');
        html += `</div>`;
        container.innerHTML = html;
        return;
    }

    // Top 3 Trending Stories in 3 Columns
    if (currentCategory === 'All' && !searchQuery && currentPage === 1) {
        const topHotPosts = allPosts.filter(p => isPostHot(p)).slice(0, 3);
        
        if (topHotPosts.length > 0) {
            html += `<div class="mb-8">`;
            html += `<div class="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider mb-4">
                        <span class="bg-amber-500/20 px-3 py-1 rounded-full border border-amber-500/40 flex items-center gap-1">🔥 Top Trending Stories</span>
                        <div class="flex-1 border-t border-amber-500/20"></div>
                     </div>`;
            
            html += `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">`;
            html += topHotPosts.map(post => {
                const isSaved = savedFiles.includes(post.file);
                return createCardHtml(post, true, isSaved);
            }).join('');
            html += `</div></div>`;
            
            html += `<div class="flex items-center gap-2 text-slate-400 text-xs font-bold uppercase tracking-wider my-6">
                        <span>📂 All Latest Articles (Non-Hot)</span>
                        <div class="flex-1 border-t border-slate-800"></div>
                     </div>`;
        }
    }

    let filteredPosts = [...allPosts];
    if (currentCategory === '🔥 Hot Topics') {
        filteredPosts = filteredPosts.filter(p => isPostHot(p));
    } else if (currentCategory !== 'All') {
        filteredPosts = filteredPosts.filter(p => (p.category || 'General') === currentCategory);
    } else if (!searchQuery) {
        const topHotFiles = new Set(allPosts.filter(p => isPostHot(p)).slice(0, 3).map(p => p.file));
        filteredPosts = filteredPosts.filter(p => !topHotFiles.has(p.file) && !isPostHot(p));
    }

    if (searchQuery) {
        filteredPosts = filteredPosts.filter(p => p.title.toLowerCase().includes(searchQuery));
    }

    if (filteredPosts.length === 0 && html === '') {
        container.innerHTML = `<p class="text-slate-500 py-10 text-center">No matching articles found.</p>`;
        return;
    }

    const totalPages = Math.ceil(filteredPosts.length / postsPerPage);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * postsPerPage;
    const end = start + postsPerPage;
    const paginatedPosts = filteredPosts.slice(start, end);

    html += `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">`;
    html += paginatedPosts.map(post => {
        const hotStatus = isPostHot(post);
        const isSaved = savedFiles.includes(post.file);
        return createCardHtml(post, hotStatus, isSaved);
    }).join('');
    html += `</div>`;

    if (totalPages > 1) {
        html += `
            <div class="flex justify-between items-center mt-10 pt-6 border-t border-slate-800/80">
                <button onclick="changePage(-1)" ${currentPage === 1 ? 'disabled class="opacity-40 cursor-not-allowed bg-slate-900 border-slate-800 px-4 py-2 rounded-xl text-xs font-semibold"' : 'class="bg-slate-900 hover:bg-slate-800 border-slate-700 text-slate-200 px-4 py-2 rounded-xl text-xs font-semibold border transition"'} >
                    &larr; Previous
                </button>
                <span class="text-xs text-slate-400 font-medium">Page ${currentPage} of ${totalPages}</span>
                <button onclick="changePage(1)" ${currentPage === totalPages ? 'disabled class="opacity-40 cursor-not-allowed bg-slate-900 border-slate-800 px-4 py-2 rounded-xl text-xs font-semibold"' : 'class="bg-slate-900 hover:bg-slate-800 border-slate-700 text-slate-200 px-4 py-2 rounded-xl text-xs font-semibold border transition"'} >
                    Next &rarr;
                </button>
            </div>
        `;
    }

    container.innerHTML = html;
}

function createCardHtml(post, hotStatus, isSaved) {
    const borderColor = hotStatus ? 'border-amber-500/30 hover:border-amber-500/60 shadow-amber-500/5' : 'border-slate-800/80 hover:border-emerald-500/50';
    const bookmarkBg = isSaved ? 'bg-blue-500 text-slate-950 border-blue-400' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-700';
    
    return `
        <div onclick="window.location.href='post.html?file=${encodeURIComponent(post.file)}'" 
             class="bg-slate-900/90 border ${borderColor} p-4 rounded-xl transition cursor-pointer group relative overflow-hidden flex flex-col justify-between shadow-md">
            <div>
                <div class="flex justify-between items-center mb-2">
                    <div class="flex items-center gap-1.5">
                        <span class="text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 px-2 py-0.5 rounded uppercase tracking-wider">
                            ${post.category || 'General'}
                        </span>
                        ${hotStatus ? `<span class="text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 px-2 py-0.5 rounded flex items-center gap-1">🔥 HOT</span>` : ''}
                    </div>
                    <div class="flex items-center gap-1">
                        <button onclick="toggleBookmark(event, '${post.file}')" title="Save for later" class="p-1.5 rounded-lg border text-xs transition ${bookmarkBg}">
                            🔖
                        </button>
                        <button onclick="shareArticle(event, '${post.title.replace(/'/g, "\\'")}', '${post.file}')" title="Share article" class="p-1.5 rounded-lg border border-slate-700 bg-slate-800/80 text-slate-300 hover:bg-slate-700 text-xs transition">
                            🔗
                        </button>
                    </div>
                </div>
                <h3 class="text-base font-bold text-slate-100 group-hover:text-emerald-400 transition mb-1 line-clamp-2">${post.title}</h3>
            </div>
            <div class="flex justify-between items-center mt-3 pt-2 border-t border-slate-800/60 text-[11px] text-slate-500">
                <span>${post.date || ''} • 4 min read</span>
                <span class="text-emerald-400 font-medium group-hover:translate-x-0.5 transition-transform">Read &rarr;</span>
            </div>
        </div>
    `;
}

fetchPosts();