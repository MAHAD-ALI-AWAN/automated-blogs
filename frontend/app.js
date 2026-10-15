let allPosts = [];
let currentCategory = 'All';
let searchQuery = '';
let currentPage = 1;
const postsPerPage = 5;
const GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/MAHAD-ALI-AWAN/automated-blogs/main';

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

async function fetchPosts() {
    const container = document.getElementById('posts-container');
    showFeedLoader();
    
    try {
        const response = await fetch(`${GITHUB_RAW_BASE}/frontend/posts.json`);
        if (!response.ok) throw new Error("Posts index nahi mila.");
        
        allPosts = await response.json();

        if (allPosts.length === 0) {
            container.innerHTML = `<p class="text-slate-500">Abhi tak koi article generate nahi hua. Pehle pipeline.py run karein!</p>`;
            return;
        }

        renderCategories();
        renderPosts();

    } catch (e) {
        container.innerHTML = `<p class="text-slate-500">Abhi tak koi article generate nahi hua. Pehle pipeline.py run karein!</p>`;
    }
}

function renderCategories() {
    const select = document.getElementById('category-select');
    const hotBtn = document.getElementById('hot-tab-btn');
    if (!select) return;
    
    const categories = ['All', ...new Set(allPosts.map(p => p.category || 'General'))];
    
    select.innerHTML = categories.map(cat => `
        <option value="${cat.replace(/'/g, "\\'")}" ${currentCategory === cat ? 'selected' : ''} class="bg-slate-900 text-slate-100 py-2">
            ${cat === 'All' ? '📂 All Categories' : cat}
        </option>
    `).join('');

    if (hotBtn) {
        if (currentCategory === '🔥 Hot Topics') {
            hotBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-amber-500 text-slate-950 border-amber-400 flex items-center justify-center gap-1.5 shrink-0 shadow-lg shadow-amber-500/20";
        } else {
            hotBtn.className = "px-4 py-2.5 rounded-xl text-xs font-bold border transition bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20 flex items-center justify-center gap-1.5 shrink-0";
        }
    }
}

function filterCategory(category) {
    currentCategory = category;
    currentPage = 1;
    renderCategories();
    renderPosts();
}

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
    
    let filteredPosts = allPosts;
    if (currentCategory === '🔥 Hot Topics') {
        filteredPosts = allPosts.filter(p => p.is_hot === true);
    } else if (currentCategory !== 'All') {
        filteredPosts = allPosts.filter(p => (p.category || 'General') === currentCategory);
    }

    if (searchQuery) {
        filteredPosts = filteredPosts.filter(p => p.title.toLowerCase().includes(searchQuery));
    }

    if (filteredPosts.length === 0) {
        container.innerHTML = `<p class="text-slate-500">Koi matching article nahi mila.</p>`;
        return;
    }

    const totalPages = Math.ceil(filteredPosts.length / postsPerPage);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * postsPerPage;
    const end = start + postsPerPage;
    const paginatedPosts = filteredPosts.slice(start, end);

    let html = paginatedPosts.map(post => `
        <div onclick="window.location.href='post.html?file=${encodeURIComponent(post.file)}'" 
             class="bg-slate-900/80 border border-slate-800/80 p-6 rounded-2xl hover:border-emerald-500/50 hover:bg-slate-900 transition cursor-pointer group relative overflow-hidden">
            <div class="flex justify-between items-center mb-3">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 px-3 py-1 rounded-full uppercase tracking-wider">
                        ${post.category || 'General'}
                    </span>
                    ${post.is_hot ? `<span class="text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 px-2 py-0.5 rounded-full flex items-center gap-1">🔥 HOT</span>` : ''}
                </div>
                <span class="text-xs text-slate-500">${post.date || ''} • ⏱️ 4 min read</span>
            </div>
            <h3 class="text-xl font-bold text-slate-100 group-hover:text-emerald-400 transition mb-2">${post.title}</h3>
            <p class="text-slate-400 text-sm line-clamp-2">Click to read full visual story, key analysis, infographics, and insights...</p>
            <div class="mt-4 text-xs font-medium text-emerald-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                Read Visual Story &rarr;
            </div>
        </div>
    `).join('');

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

fetchPosts();