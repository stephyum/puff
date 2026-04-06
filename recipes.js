// ===== STATE =====
let recipes        = [];
let unitSystem     = 'us';
let activeCategory = 'all';
let searchQuery    = '';
let searchTimer    = null;
let currentUser    = null;  // { id, username, email } or null

// ===== UNIT SYSTEM =====
function setUnitSystem(system) {
  unitSystem = system;
  document.getElementById('btn-us').classList.toggle('active', system === 'us');
  document.getElementById('btn-metric').classList.toggle('active', system === 'metric');
  renderRecipes();
  const overlay = document.getElementById('modal-overlay');
  if (overlay.classList.contains('open')) {
    const inner  = overlay.querySelector('.modal-inner');
    const id     = inner && parseInt(inner.dataset.id);
    const tab    = inner && inner.querySelector('.version-tab.active')?.dataset.tab;
    const recipe = recipes.find(r => r.id === id);
    if (recipe) {
      document.getElementById('modal-content').innerHTML = buildModal(recipe);
      if (tab) switchTab(tab);
    }
  }
}

// ===== TEMPERATURE / SIZE HELPERS =====
function renderTemp(text) {
  return unitSystem === 'metric'
    ? text.replace(/(\d+)°F\s*\((\d+)°C\)/g, '$2°C')
    : text.replace(/(\d+)°F\s*\((\d+)°C\)/g, '$1°F');
}
function renderSize(text) {
  if (unitSystem === 'metric') {
    return text
      .replace(/9×5 inch/g, '23×13 cm').replace(/8×8 inch/g, '20×20 cm')
      .replace(/8×11 inch/g, '20×28 cm').replace(/9-inch/g, '23cm')
      .replace(/8-inch/g, '20cm');
  }
  return text;
}
function renderStep(text) { return renderSize(renderTemp(text)); }
function getIng(ing) { return unitSystem === 'metric' ? ing.metric : ing.us; }

// ===== API =====
function normalize(r) {
  return {
    ...r,
    prepTime:              r.prep_time,
    cookTime:              r.cook_time,
    healthyDescription:    r.healthy_description,
    healthyCalories:       r.healthy_calories,
    healthyIngredients:    r.healthy_ingredients,
    healthySteps:          r.healthy_steps,
    healthyBenefits:       r.healthy_benefits,
    healthScore:           r.health_score,
    variants:              r.variants || {},
    avgRating:             r.avg_rating,
    reviewCount:           r.review_count,
    photoUrl:              r.photo_url || null,
    submittedBy:           r.submitted_by || null,
    submittedByUsername:   r.submitted_by_username || null,
  };
}

async function fetchRecipes() {
  const params = new URLSearchParams({ sort: 'name', order: 'asc' });
  if (searchQuery) params.set('q', searchQuery);
  if (activeCategory && activeCategory !== 'all') params.set('category', activeCategory);
  const res = await fetch('/api/recipes?' + params);
  if (!res.ok) throw new Error('API error ' + res.status);
  recipes = (await res.json()).map(normalize);
}

async function fetchCategories() {
  const res = await fetch('/api/recipes/categories');
  if (!res.ok) return [];
  return res.json();
}

// ===== STAR HELPERS =====
function starsHtml(rating, interactive, recipeId) {
  var html = '<div class="stars' + (interactive ? ' stars-interactive' : '') + '"' +
    (interactive ? ' id="star-input"' : '') + '>';
  for (var i = 1; i <= 5; i++) {
    var filled = rating && i <= rating;
    html += '<span class="star' + (filled ? ' filled' : '') + '"' +
      (interactive ? ' onclick="setStarRating(' + i + ')" data-val="' + i + '"' : '') +
      '>&#9733;</span>';
  }
  html += '</div>';
  return html;
}

var pendingRating = 0;
function setStarRating(val) {
  pendingRating = val;
  document.querySelectorAll('#star-input .star').forEach(function(s, i) {
    s.classList.toggle('filled', i < val);
  });
}

// ===== CARD =====
function buildCardMeta(recipe) {
  return '<div class="card-meta">' +
    '<span class="meta-item"><svg class="meta-icon" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z"/></svg>' + (recipe.prepTime + recipe.cookTime) + ' min</span>' +
    '<span class="meta-item"><svg class="meta-icon" viewBox="0 0 24 24"><path d="M18.06 22.99h1.66c.84 0 1.53-.64 1.63-1.46L23 5.05h-5V1h-1.97v4.05h-4.97l.3 2.34c1.71.47 3.31 1.32 4.27 2.26 1.44 1.42 2.43 2.89 2.43 5.29v8.05zM1 21.99V21h15.03v.99c0 .55-.45 1-1.01 1H2.01c-.56 0-1.01-.45-1.01-1zm15.03-7c0-8-15.03-8-15.03 0h15.03zM1.02 17h15v2H1.02v-2z"/></svg>' + recipe.calories + ' cal</span>' +
    '<span class="meta-item"><svg class="meta-icon" viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>' + recipe.servings + ' servings</span>' +
    (recipe.avgRating ? '<span class="meta-item meta-rating">' + starsHtml(Math.round(recipe.avgRating), false) + '<span class="rating-count">(' + recipe.reviewCount + ')</span></span>' : '') +
  '</div>';
}

function buildIngredientChips(ingredients) {
  const names = ingredients.slice(0, 4).map(i => {
    const text = getIng(i);
    return text.replace(/^[\d¼½¾⅓⅔⅛\s().,\w]*?\s(?=\w{3})/, '').split(',')[0].trim()
               .replace(/^\w/, c => c.toUpperCase());
  });
  const extra = ingredients.length - names.length;
  return '<div class="ingredient-chips">' +
    names.map(n => '<span class="chip">' + n + '</span>').join('') +
    (extra > 0 ? '<span class="chip chip-more">+' + extra + ' more</span>' : '') +
  '</div>';
}

function buildRecipeCard(recipe) {
  return '<article class="recipe-card">' +
    (recipe.photoUrl
      ? '<div class="card-photo" style="background-image:url(\'' + recipe.photoUrl + '\')">' +
          '<span class="category-badge card-photo-badge">' + recipe.category + '</span>' +
          '<span class="healthy-chip card-photo-chip">✦ Healthier version</span>' +
        '</div>'
      : '<div class="card-top">' +
          '<span class="category-badge">' + recipe.category + '</span>' +
          '<span class="healthy-chip">✦ Healthier version</span>' +
        '</div>'
    ) +
    '<div class="card-body">' +
      '<h2 class="recipe-name">' + recipe.name + '</h2>' +
      '<p class="recipe-desc">' + recipe.description + '</p>' +
      buildCardMeta(recipe) +
      buildIngredientChips(recipe.ingredients) +
    '</div>' +
    '<div class="card-footer">' +
      (recipe.submittedByUsername ? '<span class="card-submitted-by">by @' + recipe.submittedByUsername + '</span>' : '') +
      '<button class="view-btn" onclick="openModal(' + recipe.id + ')">' +
        '<svg viewBox="0 0 24 24" class="btn-icon"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>' +
        'View Recipe' +
      '</button>' +
      (currentUser && recipe.submittedBy === currentUser.id
        ? '<button class="delete-recipe-btn" onclick="deleteUserRecipe(event,' + recipe.id + ')">Delete</button>'
        : '') +
    '</div>' +
  '</article>';
}

// ===== MODAL =====
function buildIngredientsList(ingredients, isVariant) {
  return '<ul class="ingredients-list">' +
    ingredients.map(function(i) {
      if (isVariant && i.swap) {
        var fromText = unitSystem === 'metric' ? i.swap_from_metric : i.swap_from_us;
        return '<li class="ingredient-swapped">' +
          '<div class="swap-new">' + getIng(i) + '</div>' +
          '<div class="swap-from">was: ' + fromText + '</div>' +
          '<div class="swap-reason">&#8593; ' + i.swap_reason + '</div>' +
        '</li>';
      }
      return '<li>' + getIng(i) + '</li>';
    }).join('') +
  '</ul>';
}

function buildStepsList(steps) {
  return '<ol class="steps-list">' +
    steps.map(function(s, i) {
      return '<li class="step-item">' +
        '<span class="step-number">' + (i + 1) + '</span>' +
        '<span class="step-text">' + renderStep(s) + '</span>' +
      '</li>';
    }).join('') +
  '</ol>';
}

var VARIANT_META = {
  healthy:      { label: '✦ Healthier',   cls: 'healthy-tab',     icon: '🌿' },
  vegan:        { label: '🌱 Vegan',       cls: 'vegan-tab',       icon: '🌱' },
  'gluten-free':{ label: '🌾 Gluten-Free', cls: 'gluten-free-tab', icon: '🌾' },
};

function buildVariantBanner(variant, variantType, originalCalories) {
  var meta      = VARIANT_META[variantType] || { icon: '✦', label: variantType };
  var calSaving = originalCalories - variant.calories;
  var calPct    = Math.round((calSaving / originalCalories) * 100);
  return '<div class="healthy-banner">' +
    '<div class="healthy-banner-icon">' + meta.icon + '</div>' +
    '<div class="healthy-banner-body">' +
      '<div class="healthy-banner-title">' + meta.label + ' Version</div>' +
      '<div class="healthy-banner-desc">' + variant.description + '</div>' +
      '<div class="calorie-comparison">' +
        '<span class="cal-old">' + originalCalories + ' cal</span>' +
        '<span class="cal-arrow">&#8594;</span>' +
        '<span class="cal-new">' + variant.calories + ' cal</span>' +
        (calSaving > 0 ? '<span class="cal-save">&#8722;' + calPct + '% calories</span>' : '') +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildAIGenerateSection(recipeId) {
  var types = [
    { type: 'healthy',     label: '✦ Healthier',   cls: 'ai-btn-healthy' },
    { type: 'vegan',       label: '🌱 Vegan',       cls: 'ai-btn-vegan'   },
    { type: 'gluten-free', label: '🌾 Gluten-Free', cls: 'ai-btn-gf'      },
  ];
  return '<div class="ai-generate-section">' +
    '<p class="ai-generate-label">Explore more versions:</p>' +
    '<div class="ai-btn-row">' +
    types.map(function(t) {
      return '<button class="ai-gen-btn ' + t.cls + '" onclick="generateVariant(' + recipeId + ',\'' + t.type + '\')">' +
        t.label + '</button>';
    }).join('') +
    '</div>' +
  '</div>';
}

function buildModal(recipe) {
  var calSaving = recipe.calories - recipe.healthyCalories;
  var calPct    = Math.round((calSaving / recipe.calories) * 100);
  var variants  = recipe.variants || {};
  var extraTabs = Object.keys(variants).filter(function(k) { return k !== 'healthy'; });

  var tabs =
    '<button class="version-tab active" data-tab="classic" onclick="switchTab(\'classic\')">Classic</button>' +
    '<button class="version-tab healthy-tab" data-tab="healthy" onclick="switchTab(\'healthy\')">✦ Healthier</button>' +
    extraTabs.map(function(vt) {
      var meta = VARIANT_META[vt] || { label: vt, cls: '' };
      return '<button class="version-tab ' + meta.cls + '" data-tab="variant-' + vt + '" onclick="switchTab(\'variant-' + vt + '\')">' +
        meta.label + '</button>';
    }).join('') +
    '<button class="version-tab reviews-tab" data-tab="reviews" onclick="switchTab(\'reviews\');loadReviews(' + recipe.id + ')">&#9733; Reviews' +
      (recipe.reviewCount ? ' <span style="opacity:.6;font-weight:400">(' + recipe.reviewCount + ')</span>' : '') +
    '</button>';

  var extraPanels = extraTabs.map(function(vt) {
    var v = variants[vt];
    return '<div class="tab-panel" data-tab="variant-' + vt + '">' +
      buildVariantBanner(v, vt, recipe.calories) +
      '<ul class="benefits-list">' +
        v.benefits.map(function(b) {
          return '<li><span class="benefit-check">&#10003;</span>' + b + '</li>';
        }).join('') +
      '</ul>' +
      '<div class="recipe-two-col">' +
        '<div><p class="section-title">Ingredients <span style="color:var(--amber-500);font-size:.7rem;margin-left:4px;">highlighted = swapped</span></p>' +
          buildIngredientsList(v.ingredients, true) +
        '</div>' +
        '<div><p class="section-title">Instructions</p>' + buildStepsList(v.steps) + '</div>' +
      '</div>' +
    '</div>';
  }).join('');

  return '<div class="modal-inner" data-id="' + recipe.id + '">' +
    '<button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>' +

    (recipe.photoUrl
      ? '<div class="modal-hero" style="background-image:url(\'' + recipe.photoUrl + '\')"></div>'
      : '') +

    '<div class="modal-header">' +
      '<div>' +
        '<span class="category-badge modal-category-badge">' + recipe.category + '</span>' +
        '<h2 class="modal-recipe-name">' + recipe.name + '</h2>' +
        buildCardMeta(recipe) +
      '</div>' +
    '</div>' +

    '<div class="version-tabs">' + tabs + '</div>' +

    // Classic tab
    '<div class="tab-panel active" data-tab="classic">' +
      buildAIGenerateSection(recipe.id) +
      '<div class="recipe-two-col">' +
        '<div><p class="section-title">Ingredients</p>' + buildIngredientsList(recipe.ingredients, false) + '</div>' +
        '<div><p class="section-title">Instructions</p>' + buildStepsList(recipe.steps) + '</div>' +
      '</div>' +
    '</div>' +

    // Built-in Healthier tab
    '<div class="tab-panel" data-tab="healthy">' +
      '<div class="healthy-banner">' +
        '<div class="healthy-banner-icon">&#127807;</div>' +
        '<div class="healthy-banner-body">' +
          '<div class="healthy-banner-title">Healthier Version</div>' +
          '<div class="healthy-banner-desc">' + recipe.healthyDescription + '</div>' +
          '<div class="calorie-comparison">' +
            '<span class="cal-old">' + recipe.calories + ' cal</span>' +
            '<span class="cal-arrow">&#8594;</span>' +
            '<span class="cal-new">' + recipe.healthyCalories + ' cal</span>' +
            (calSaving > 0 ? '<span class="cal-save">&#8722;' + calPct + '% calories</span>' : '') +
          '</div>' +
        '</div>' +
      '</div>' +
      '<ul class="benefits-list">' +
        recipe.healthyBenefits.map(function(b) {
          return '<li><span class="benefit-check">&#10003;</span>' + b + '</li>';
        }).join('') +
      '</ul>' +
      '<div class="recipe-two-col">' +
        '<div><p class="section-title">Ingredients <span style="color:var(--amber-500);font-size:.7rem;margin-left:4px;">highlighted = swapped</span></p>' +
          buildIngredientsList(recipe.healthyIngredients, true) +
        '</div>' +
        '<div><p class="section-title">Instructions</p>' + buildStepsList(recipe.healthySteps) + '</div>' +
      '</div>' +
    '</div>' +

    extraPanels +

    // Reviews tab
    '<div class="tab-panel" data-tab="reviews" id="reviews-panel-' + recipe.id + '">' +
      '<div class="reviews-loading">Loading reviews\u2026</div>' +
    '</div>' +

  '</div>';
}

function switchTab(tab) {
  document.querySelectorAll('.version-tab').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-panel').forEach(function(panel) {
    panel.classList.toggle('active', panel.dataset.tab === tab);
  });
}

function openModal(id) {
  var recipe = recipes.find(function(r) { return r.id === id; });
  if (!recipe) return;
  document.getElementById('modal-content').innerHTML = buildModal(recipe);
  document.getElementById('modal-overlay').classList.add('open');
  document.body.classList.add('modal-open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.classList.remove('modal-open');
}

// ===== AI VARIANT GENERATION =====
async function generateVariant(recipeId, variantType) {
  var recipe = recipes.find(function(r) { return r.id === recipeId; });
  if (!recipe) return;

  if (recipe.variants && recipe.variants[variantType]) {
    switchTab('variant-' + variantType);
    return;
  }

  var btn = document.querySelector('.ai-gen-btn[onclick*="\'' + variantType + '\'"]');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="ai-spinner"></span> Loading\u2026';
  }

  try {
    var res = await fetch('/api/recipes/' + recipeId + '/adapt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant_type: variantType }),
    });
    if (!res.ok) {
      var err = await res.json().catch(function() { return {}; });
      throw new Error(err.error || 'Server error ' + res.status);
    }
    var variant = await res.json();
    if (!recipe.variants) recipe.variants = {};
    recipe.variants[variantType] = variant;
    document.getElementById('modal-content').innerHTML = buildModal(recipe);
    switchTab('variant-' + variantType);
  } catch(e) {
    if (btn) {
      btn.disabled = false;
      var meta = VARIANT_META[variantType] || { label: variantType };
      btn.innerHTML = meta.label;
    }
    alert('Could not generate variant: ' + e.message);
  }
}

// ===== REVIEWS =====
async function loadReviews(recipeId) {
  var panel = document.getElementById('reviews-panel-' + recipeId);
  if (!panel) return;

  var res  = await fetch('/api/recipes/' + recipeId + '/reviews');
  var data = await res.json();
  var reviews    = data.reviews || [];
  var myReviewId = data.my_review_id;

  var html = '';

  // Write-a-review form
  if (currentUser) {
    var existing = reviews.find(function(r) { return r.username === currentUser.username; });
    pendingRating = existing ? existing.rating : 0;
    html += '<div class="review-form">' +
      '<p class="section-title">Your Review</p>' +
      starsHtml(pendingRating, true, recipeId) +
      '<textarea id="review-comment" class="review-textarea" placeholder="Share your experience\u2026" rows="3">' +
        (existing ? (existing.comment || '') : '') +
      '</textarea>' +
      '<div class="review-form-actions">' +
        '<button class="review-submit-btn" onclick="submitReview(' + recipeId + ')">' +
          (existing ? 'Update review' : 'Post review') +
        '</button>' +
        (myReviewId ? '<button class="review-delete-btn" onclick="deleteReview(' + myReviewId + ',' + recipeId + ')">Delete</button>' : '') +
      '</div>' +
    '</div>';
  } else {
    html += '<div class="review-login-prompt">' +
      '<a href="#" onclick="openAuth(\'login\');return false">Log in</a> or ' +
      '<a href="#" onclick="openAuth(\'register\');return false">sign up</a> to leave a review.' +
    '</div>';
  }

  // Reviews list
  if (reviews.length === 0) {
    html += '<p class="reviews-empty">No reviews yet. Be the first!</p>';
  } else {
    html += '<div class="reviews-list">';
    reviews.forEach(function(r) {
      html += '<div class="review-card">' +
        '<div class="review-header">' +
          '<span class="review-author">' + r.username + '</span>' +
          starsHtml(r.rating, false) +
          '<span class="review-date">' + new Date(r.created_at).toLocaleDateString() + '</span>' +
        '</div>' +
        (r.comment ? '<p class="review-comment">' + r.comment + '</p>' : '') +
      '</div>';
    });
    html += '</div>';
  }

  panel.innerHTML = html;
}

async function submitReview(recipeId) {
  if (!currentUser) { openAuth('login'); return; }
  if (!pendingRating) { alert('Please select a star rating.'); return; }
  var comment = (document.getElementById('review-comment').value || '').trim();

  var res = await fetch('/api/recipes/' + recipeId + '/reviews', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ rating: pendingRating, comment: comment }),
  });
  if (!res.ok) {
    var err = await res.json().catch(function() { return {}; });
    alert('Error: ' + (err.error || res.status));
    return;
  }
  // Refresh reviews and update recipe avg in local state
  await loadReviews(recipeId);
  var recipe = recipes.find(function(r) { return r.id === recipeId; });
  if (recipe) {
    var reviewsRes = await fetch('/api/recipes/' + recipeId + '/reviews');
    var reviewsData = await reviewsRes.json();
    var list = reviewsData.reviews || [];
    recipe.reviewCount = list.length;
    recipe.avgRating   = list.length
      ? Math.round(list.reduce(function(s, r) { return s + r.rating; }, 0) / list.length * 10) / 10
      : null;
  }
}

async function deleteReview(reviewId, recipeId) {
  if (!confirm('Delete your review?')) return;
  var res = await fetch('/api/reviews/' + reviewId, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) { alert('Could not delete review.'); return; }
  await loadReviews(recipeId);
}

// ===== AUTH =====
function openAuth(mode) {
  document.getElementById('auth-modal-body').innerHTML = buildAuthForm(mode);
  document.getElementById('auth-overlay').classList.add('open');
  document.body.classList.add('modal-open');
}

function closeAuth() {
  document.getElementById('auth-overlay').classList.remove('open');
  document.body.classList.remove('modal-open');
}

function buildAuthForm(mode) {
  var isLogin = mode === 'login';
  return '<h2 class="auth-title">' + (isLogin ? 'Log in' : 'Create account') + '</h2>' +
    '<form class="auth-form" onsubmit="handleAuth(event,\'' + mode + '\')">' +
    (!isLogin ? '<div class="auth-field"><label>Username</label><input type="text" name="username" required minlength="2" placeholder="e.g. bakerJane" /></div>' : '') +
    '<div class="auth-field"><label>Email</label><input type="email" name="email" required placeholder="you@example.com" /></div>' +
    '<div class="auth-field"><label>Password</label><input type="password" name="password" required minlength="6" placeholder="At least 6 characters" /></div>' +
    '<div id="auth-error" class="auth-error"></div>' +
    '<button type="submit" class="auth-submit-btn">' + (isLogin ? 'Log in' : 'Sign up') + '</button>' +
    '</form>' +
    '<p class="auth-switch">' +
      (isLogin
        ? 'No account? <a href="#" onclick="openAuth(\'register\');return false">Sign up</a>'
        : 'Already have an account? <a href="#" onclick="openAuth(\'login\');return false">Log in</a>') +
    '</p>';
}

async function handleAuth(e, mode) {
  e.preventDefault();
  var form = e.target;
  var errEl = document.getElementById('auth-error');
  errEl.textContent = '';

  var body = {
    email:    form.email.value.trim(),
    password: form.password.value,
  };
  if (mode === 'register') body.username = form.username.value.trim();

  var res  = await fetch('/api/auth/' + (mode === 'login' ? 'login' : 'register'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  var data = await res.json();
  if (!res.ok) {
    errEl.textContent = data.error || 'Something went wrong.';
    return;
  }
  currentUser = data;
  updateUserUI();
  closeAuth();
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  currentUser = null;
  updateUserUI();
}

function updateUserUI() {
  var guest    = document.getElementById('user-guest');
  var loggedin = document.getElementById('user-loggedin');
  var greeting = document.getElementById('user-greeting');
  if (currentUser) {
    guest.style.display    = 'none';
    loggedin.style.display = 'flex';
    greeting.textContent   = 'Hi, ' + currentUser.username + '!';
  } else {
    guest.style.display    = 'flex';
    loggedin.style.display = 'none';
  }
}

// ===== SUBMIT RECIPE =====
var RECIPE_CATEGORIES = [
  'Cookies','Cakes','Muffins','Breads','Bars & Brownies',
  'Cheesecakes','Pies & Tarts','Scones & Biscuits',
  'French Pastries','Italian Desserts','Japanese Sweets','Other'
];

function openSubmitRecipe() {
  document.getElementById('submit-recipe-body').innerHTML = buildSubmitForm();
  document.getElementById('submit-recipe-overlay').classList.add('open');
  document.body.classList.add('modal-open');
}

function closeSubmitRecipe() {
  document.getElementById('submit-recipe-overlay').classList.remove('open');
  document.body.classList.remove('modal-open');
}

function buildSubmitForm() {
  return '<h2 class="auth-title">Share a Recipe</h2>' +
  '<form class="submit-recipe-form" onsubmit="handleSubmitRecipe(event)">' +

  '<div class="submit-two-col">' +
    '<div class="auth-field">' +
      '<label>Recipe name *</label>' +
      '<input type="text" name="name" required placeholder="e.g. Lemon Poppy Seed Cake" />' +
    '</div>' +
    '<div class="auth-field">' +
      '<label>Category *</label>' +
      '<select name="category" required>' +
        RECIPE_CATEGORIES.map(function(c) { return '<option value="' + c + '">' + c + '</option>'; }).join('') +
      '</select>' +
    '</div>' +
  '</div>' +

  '<div class="auth-field">' +
    '<label>Description *</label>' +
    '<textarea name="description" required rows="2" placeholder="A short description of your recipe…"></textarea>' +
  '</div>' +

  '<div class="submit-four-col">' +
    '<div class="auth-field"><label>Calories / serving *</label><input type="number" name="calories" required min="1" placeholder="e.g. 320" /></div>' +
    '<div class="auth-field"><label>Servings *</label><input type="number" name="servings" required min="1" placeholder="e.g. 12" /></div>' +
    '<div class="auth-field"><label>Prep time (min) *</label><input type="number" name="prep_time" required min="0" placeholder="e.g. 15" /></div>' +
    '<div class="auth-field"><label>Cook time (min) *</label><input type="number" name="cook_time" required min="0" placeholder="e.g. 30" /></div>' +
  '</div>' +

  '<div class="auth-field">' +
    '<label>Ingredients *</label>' +
    '<div id="ing-list">' +
      '<div class="dynamic-row"><input type="text" class="ing-input" placeholder="e.g. 2 cups all-purpose flour" /><button type="button" class="row-remove-btn" onclick="removeRow(this)">×</button></div>' +
    '</div>' +
    '<button type="button" class="row-add-btn" onclick="addIngredient()">+ Add ingredient</button>' +
  '</div>' +

  '<div class="auth-field">' +
    '<label>Steps *</label>' +
    '<div id="steps-list">' +
      '<div class="dynamic-row dynamic-row-step"><span class="step-num">1</span><textarea class="step-input" rows="2" placeholder="Describe this step…"></textarea><button type="button" class="row-remove-btn" onclick="removeRow(this)">×</button></div>' +
    '</div>' +
    '<button type="button" class="row-add-btn" onclick="addStep()">+ Add step</button>' +
  '</div>' +

  '<div id="submit-recipe-error" class="auth-error"></div>' +
  '<button type="submit" class="auth-submit-btn">Publish Recipe</button>' +
  '</form>';
}

function addIngredient() {
  var list = document.getElementById('ing-list');
  var div = document.createElement('div');
  div.className = 'dynamic-row';
  div.innerHTML = '<input type="text" class="ing-input" placeholder="e.g. 1 tsp vanilla extract" />' +
    '<button type="button" class="row-remove-btn" onclick="removeRow(this)">×</button>';
  list.appendChild(div);
}

function addStep() {
  var list = document.getElementById('steps-list');
  var num  = list.querySelectorAll('.dynamic-row').length + 1;
  var div  = document.createElement('div');
  div.className = 'dynamic-row dynamic-row-step';
  div.innerHTML = '<span class="step-num">' + num + '</span>' +
    '<textarea class="step-input" rows="2" placeholder="Describe this step…"></textarea>' +
    '<button type="button" class="row-remove-btn" onclick="removeRow(this)">×</button>';
  list.appendChild(div);
  renumberSteps();
}

function removeRow(btn) {
  btn.closest('.dynamic-row').remove();
  renumberSteps();
}

function renumberSteps() {
  document.querySelectorAll('#steps-list .step-num').forEach(function(el, i) {
    el.textContent = i + 1;
  });
}

async function handleSubmitRecipe(e) {
  e.preventDefault();
  var form  = e.target;
  var errEl = document.getElementById('submit-recipe-error');
  errEl.textContent = '';

  var ingredients = Array.from(document.querySelectorAll('.ing-input'))
    .map(function(el) { return el.value.trim(); })
    .filter(Boolean);
  var steps = Array.from(document.querySelectorAll('.step-input'))
    .map(function(el) { return el.value.trim(); })
    .filter(Boolean);

  if (ingredients.length === 0) { errEl.textContent = 'Add at least one ingredient.'; return; }
  if (steps.length === 0)       { errEl.textContent = 'Add at least one step.'; return; }

  var body = {
    name:        form.name.value.trim(),
    category:    form.category.value,
    description: form.description.value.trim(),
    calories:    parseInt(form.calories.value),
    servings:    parseInt(form.servings.value),
    prep_time:   parseInt(form.prep_time.value),
    cook_time:   parseInt(form.cook_time.value),
    ingredients: ingredients,
    steps:       steps,
  };

  var submitBtn = form.querySelector('[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Publishing…';

  var res = await fetch('/api/my-recipes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  var data = await res.json();
  if (!res.ok) {
    errEl.textContent = data.error || 'Something went wrong.';
    submitBtn.disabled = false;
    submitBtn.textContent = 'Publish Recipe';
    return;
  }

  closeSubmitRecipe();
  await renderRecipes();
  // Open the newly created recipe
  openModal(data.id);
}

async function deleteUserRecipe(e, recipeId) {
  e.stopPropagation();
  if (!confirm('Delete your recipe? This cannot be undone.')) return;
  var res = await fetch('/api/my-recipes/' + recipeId, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) { alert('Could not delete recipe.'); return; }
  await renderRecipes();
}

// ===== RENDER =====
async function renderRecipes() {
  var grid    = document.getElementById('recipe-grid');
  var countEl = document.getElementById('recipe-count');
  grid.innerHTML = '<div class="empty-state"><p>Loading\u2026</p></div>';

  try { await fetchRecipes(); }
  catch(e) {
    grid.innerHTML = '<div class="empty-state"><p>Could not load recipes. Is the server running?</p></div>';
    return;
  }

  if (recipes.length === 0) {
    grid.innerHTML = '<div class="empty-state"><p>No recipes found' + (searchQuery ? ' for \u201c' + searchQuery + '\u201d' : '') + '. Try a different search.</p></div>';
    countEl.textContent = '';
    return;
  }

  grid.innerHTML = recipes.map(buildRecipeCard).join('');
  countEl.textContent = recipes.length + ' recipe' + (recipes.length !== 1 ? 's' : '') + ' found';

  requestAnimationFrame(function() {
    grid.querySelectorAll('.recipe-card').forEach(function(card, i) {
      card.style.animationDelay = (i * 50) + 'ms';
      card.classList.add('animate-in');
    });
  });
}

async function renderCategoryTabs() {
  var bar  = document.getElementById('category-tabs');
  var cats = await fetchCategories();
  var total = cats.reduce(function(s, c) { return s + c.count; }, 0);
  var all  = [{ category: 'all', count: total }].concat(cats);
  bar.innerHTML = all.map(function(c) {
    var label = c.category === 'all' ? 'All' : c.category;
    return '<button class="cat-tab' + (activeCategory === c.category ? ' active' : '') + '" onclick="setCategory(\'' + c.category + '\')">' +
      label + ' <span style="opacity:.6;font-weight:400">' + c.count + '</span></button>';
  }).join('');
}

async function setCategory(cat) {
  activeCategory = cat;
  await renderCategoryTabs();
  await renderRecipes();
}

function onSearch(value) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async function() {
    searchQuery = value.trim();
    await renderRecipes();
  }, 300);
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', async function() {
  // Check if already logged in
  var meRes = await fetch('/api/auth/me', { credentials: 'include' });
  currentUser = await meRes.json();
  updateUserUI();

  await renderCategoryTabs();
  await renderRecipes();

  document.getElementById('search-input').addEventListener('input', function(e) {
    onSearch(e.target.value);
  });

  document.getElementById('modal-overlay').addEventListener('click', function(e) {
    if (e.target === e.currentTarget) closeModal();
  });

  document.getElementById('auth-overlay').addEventListener('click', function(e) {
    if (e.target === e.currentTarget) closeAuth();
  });

  document.getElementById('submit-recipe-overlay').addEventListener('click', function(e) {
    if (e.target === e.currentTarget) closeSubmitRecipe();
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { closeModal(); closeAuth(); closeSubmitRecipe(); }
  });
});
