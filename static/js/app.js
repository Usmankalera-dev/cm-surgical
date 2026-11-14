(function () {
  "use strict";

  const CART_KEY = "ssi_cart";
  const WISH_KEY = "ssi_wishlist";
  const COUPON_KEY = "ssi_coupon";

  // ---------- Cart (localStorage) ----------
  function getCart() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY)) || [];
    } catch (e) {
      return [];
    }
  }
  function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartBadge();
    window.dispatchEvent(new CustomEvent("cart:updated"));
  }
  function addToCart(product, qty) {
    const cart = getCart();
    qty = Math.min(qty, product.stock || 99);
    const existing = cart.find((i) => i.id === product.id);
    if (existing) existing.quantity = Math.min(existing.quantity + qty, product.stock || 99);
    else {
      cart.push({
        id: product.id,
        sku: product.sku,
        name: product.name,
        image: product.image,
        category: product.category,
        price: product.price_max || product.price_min,
        stock: product.stock || 99,
        quantity: qty,
      });
    }
    saveCart(cart);
  }
  function updateCartBadge() {
    const total = getCart().reduce((s, i) => s + i.quantity, 0);
    document.querySelectorAll("#cartCount").forEach((el) => (el.textContent = total));
  }
  function fmt(n) {
    return "₨ " + n.toLocaleString("en-PK");
  }

  const endpoint = (path) => path;
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- Wishlist (localStorage) ----------
  function getWishlist() {
    try {
      return (JSON.parse(localStorage.getItem(WISH_KEY)) || []).map(Number);
    } catch (e) {
      return [];
    }
  }
  function saveWishlist(ids) {
    localStorage.setItem(WISH_KEY, JSON.stringify([...new Set(ids.map(Number))]));
    updateWishlistUI();
    window.dispatchEvent(new CustomEvent("wishlist:updated"));
  }
  function inWishlist(id) {
    return getWishlist().indexOf(Number(id)) !== -1;
  }
  function toggleWishlist(id) {
    id = Number(id);
    const list = getWishlist();
    const i = list.indexOf(id);
    if (i === -1) list.push(id);
    else list.splice(i, 1);
    saveWishlist(list);
    return list.indexOf(id) !== -1;
  }
  function updateWishlistUI() {
    const count = getWishlist().length;
    document.querySelectorAll("#wishCount").forEach((el) => (el.textContent = count));
    document.querySelectorAll("[data-wish]").forEach((btn) => {
      const on = inWishlist(btn.dataset.wish);
      btn.classList.toggle("active", on);
      if (btn.id === "wishBtn") btn.innerHTML = on ? "♥ Saved" : "♥ Save";
    });
  }

  // ---------- Coupon state (localStorage) ----------
  function getCoupon() {
    try {
      return JSON.parse(localStorage.getItem(COUPON_KEY)) || null;
    } catch (e) {
      return null;
    }
  }
  function setCoupon(c) {
    if (c) localStorage.setItem(COUPON_KEY, JSON.stringify(c));
    else localStorage.removeItem(COUPON_KEY);
  }

  // ---------- Shared product card markup ----------
  function starsHTML(rating) {
    if (!rating) return "";
    let out = '<span class="stars">';
    for (let i = 1; i <= 5; i++) out += '<span class="' + (i <= Math.round(rating) ? "star-on" : "star-off") + '">★</span>';
    return out + "</span>";
  }
  function cardHTML(p) {
    const price =
      p.price_min === p.price_max
        ? "₨ " + p.price_min_str + ' <span class="small muted">excl. GST</span>'
        : "₨ " + p.price_min_str + " – ₨ " + p.price_max_str + ' <span class="small muted">excl. GST</span>';
    const badge =
      p.stock === 0
        ? '<span class="oos-badge">Out of Stock</span>'
        : p.stock < 10
        ? '<span class="low-badge">Only ' + p.stock + " left</span>"
        : "";
    const rating = p.review_count
      ? '<a class="rating-line" href="/product/' + p.id + '#reviews">' + starsHTML(p.rating) + '<span class="small muted">' + p.rating + " (" + p.review_count + ")</span></a>"
      : '<a class="rating-line muted small" href="/product/' + p.id + '#reviews">No reviews yet</a>';
    return (
      '<a class="product-card" href="/product/' + p.id + '">' +
      '<span class="product-img"><img src="' + esc(p.image) + '" alt="' + esc(p.name) + '" loading="lazy">' + badge +
      '<button class="wish-btn' + (inWishlist(p.id) ? " active" : "") + '" data-wish="' + p.id + '" aria-label="Save to wishlist" title="Save to wishlist">♥</button></span>' +
      '<span class="product-body"><span class="product-cat">' + esc(p.category) + "</span>" +
      '<span class="product-name">' + esc(p.name) + "</span>" +
      '<span class="product-rating">' + rating + "</span>" +
      '<span class="product-price">' + price + "</span></span>" +
      '<span class="product-actions">' +
      (p.stock > 0
        ? '<button class="btn btn-primary btn-small btn-add" data-add data-id="' + p.id + '" data-name="' + esc(p.name) + '" data-price="' + (p.price_max || p.price_min) + '" data-image="' + esc(p.image) + '" data-stock="' + p.stock + '" data-category="' + esc(p.category) + '">Add to Cart</button>'
        : '<button class="btn btn-small btn-add" disabled>Out of Stock</button>') +
      "</span></a>"
    );
  }

  // ---------- Header search suggestions ----------
  function initSearchSuggest() {
    const input = document.getElementById("siteSearch");
    const box = document.getElementById("searchSuggest");
    if (!input || !box) return;
    let timer = null;

    function hide() {
      box.hidden = true;
      box.innerHTML = "";
    }
    function render(list) {
      if (!list.length) return hide();
      box.innerHTML = list
        .map(
          (p) =>
            '<a href="/product/' + p.id + '"><img src="' + esc(p.image) + '" alt=""><span class="sg-body">' +
            "<strong>" + esc(p.name) + "</strong><span>" + esc(p.sku) + " · " + esc(p.category) +
            (p.in_stock ? "" : " · Out of stock") + "</span></span>" +
            '<span class="sg-price">' + fmt(p.price) + "</span></a>"
        )
        .join("");
      box.hidden = false;
    }
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) return hide();
      timer = setTimeout(() => {
        fetch(endpoint("/api/search/suggest?q=" + encodeURIComponent(q)))
          .then((r) => r.json())
          .then(render)
          .catch(hide);
      }, 180);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hide();
      if (e.key === "Enter" && !box.hidden) {
        const first = box.querySelector("a");
        if (first) {
          e.preventDefault();
          window.location.href = first.getAttribute("href");
        }
      }
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search-wrap")) hide();
    });
  }

  // ---------- Shop page ----------
  function initShop() {
    const grid = document.getElementById("productGrid");
    if (!grid) return;
    const countEl = document.getElementById("resultCount");
    const emptyEl = document.getElementById("emptyMsg");
    const sortEl = document.getElementById("sortSelect");
    const searchEl = document.getElementById("shopSearch");
    const minEl = document.getElementById("fMin");
    const maxEl = document.getElementById("fMax");
    const stockEl = document.getElementById("fStock");
    const topEl = document.getElementById("fTop");
    const chipsEl = document.getElementById("activeFilters");

    const url = new URL(window.location.href);
    const state = {
      category: url.searchParams.get("category") || "",
      search: url.searchParams.get("search") || "",
      min_price: url.searchParams.get("min_price") || "",
      max_price: url.searchParams.get("max_price") || "",
      in_stock: url.searchParams.get("in_stock") || "",
      top_sell: url.searchParams.get("top_sell") || "",
      sort: url.searchParams.get("sort") || "name",
    };

    if (searchEl) searchEl.value = state.search;
    if (minEl) minEl.value = state.min_price;
    if (maxEl) maxEl.value = state.max_price;
    if (stockEl) stockEl.checked = !!state.in_stock;
    if (topEl) topEl.checked = !!state.top_sell;
    if (sortEl) sortEl.value = state.sort;

    document.querySelectorAll(".cat-link").forEach((a) => {
      if ((a.dataset.slug || "") === state.category) a.classList.add("active");
    });

    function chips() {
      const out = [];
      if (state.search) out.push(["search", "Search: " + state.search]);
      if (state.min_price) out.push(["min_price", "Min ₨ " + Number(state.min_price).toLocaleString("en-PK")]);
      if (state.max_price) out.push(["max_price", "Max ₨ " + Number(state.max_price).toLocaleString("en-PK")]);
      if (state.in_stock) out.push(["in_stock", "In stock"]);
      if (state.top_sell) out.push(["top_sell", "Top sellers"]);
      if (!chipsEl) return;
      if (!out.length) {
        chipsEl.hidden = true;
        chipsEl.innerHTML = "";
        return;
      }
      chipsEl.hidden = false;
      chipsEl.innerHTML =
        out.map(([k, label]) => '<button class="chip" data-clear="' + k + '">' + esc(label) + " ✕</button>").join("") +
        '<button class="chip chip-clear" data-clear="all">Clear all</button>';
    }

    function syncURL() {
      const p = new URLSearchParams();
      Object.keys(state).forEach((k) => {
        if (state[k] && !(k === "sort" && state[k] === "name")) p.set(k, state[k]);
      });
      const qs = p.toString();
      history.replaceState(null, "", qs ? "/shop?" + qs : "/shop");
    }

    function load() {
      syncURL();
      chips();
      const params = new URLSearchParams();
      if (state.category) params.set("category", state.category);
      if (state.search) params.set("search", state.search);
      if (state.min_price) params.set("min_price", state.min_price);
      if (state.max_price) params.set("max_price", state.max_price);
      if (state.in_stock) params.set("in_stock", "1");
      if (state.top_sell) params.set("top_sell", "1");
      params.set("sort", state.sort || "name");
      countEl.textContent = "Loading…";
      fetch(endpoint("/api/products?" + params.toString()))
        .then((r) => r.json())
        .then((list) => {
          if (!list.length) {
            grid.innerHTML = "";
            emptyEl.hidden = false;
            countEl.textContent = "0 products";
            return;
          }
          emptyEl.hidden = true;
          countEl.textContent = list.length + " product" + (list.length === 1 ? "" : "s");
          grid.innerHTML = list.map(cardHTML).join("");
        })
        .catch(() => {
          emptyEl.hidden = false;
          countEl.textContent = "0 products";
        });
    }

    if (sortEl) sortEl.addEventListener("change", () => ((state.sort = sortEl.value), load()));
    if (searchEl) {
      let t = null;
      searchEl.addEventListener("input", () => {
        clearTimeout(t);
        t = setTimeout(() => {
          state.search = searchEl.value.trim();
          load();
        }, 250);
      });
    }
    if (minEl) minEl.addEventListener("change", () => ((state.min_price = minEl.value), load()));
    if (maxEl) maxEl.addEventListener("change", () => ((state.max_price = maxEl.value), load()));
    if (stockEl) stockEl.addEventListener("change", () => ((state.in_stock = stockEl.checked ? "1" : ""), load()));
    if (topEl) topEl.addEventListener("change", () => ((state.top_sell = topEl.checked ? "1" : ""), load()));

    const reset = document.getElementById("fReset");
    if (reset)
      reset.addEventListener("click", () => {
        Object.assign(state, { min_price: "", max_price: "", in_stock: "", top_sell: "" });
        if (minEl) minEl.value = "";
        if (maxEl) maxEl.value = "";
        if (stockEl) stockEl.checked = false;
        if (topEl) topEl.checked = false;
        load();
      });

    if (chipsEl)
      chipsEl.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-clear]");
        if (!btn) return;
        const key = btn.dataset.clear;
        if (key === "all") {
          Object.assign(state, { search: "", min_price: "", max_price: "", in_stock: "", top_sell: "" });
          if (searchEl) searchEl.value = "";
          if (minEl) minEl.value = "";
          if (maxEl) maxEl.value = "";
          if (stockEl) stockEl.checked = false;
          if (topEl) topEl.checked = false;
        } else {
          state[key] = "";
          if (key === "search" && searchEl) searchEl.value = "";
          if (key === "min_price" && minEl) minEl.value = "";
          if (key === "max_price" && maxEl) maxEl.value = "";
          if (key === "in_stock" && stockEl) stockEl.checked = false;
          if (key === "top_sell" && topEl) topEl.checked = false;
        }
        load();
      });

    load();
  }

  // ---------- Product detail ----------
  function initProduct() {
    const btn = document.getElementById("addToCartBtn");
    if (!btn) return;
    const qty = document.getElementById("qty");
    const max = parseInt(qty.dataset.max || "99", 10);
    const getQty = () => Math.max(1, Math.min(max, parseInt(qty.value || "1", 10)));
    const waBtn = document.getElementById("waOrderBtn");
    const updateWaLink = () => {
      if (!waBtn) return;
      const p = window.__PRODUCT__;
      const msg =
        "Hello CM SURGICAL, I want to order:\n\n• " +
        p.name + " (SKU: " + p.sku + ")\n• Quantity: " + getQty() +
        "\n• Price: ₨ " + (p.price_min_str || p.price_min) + " (excl. GST)\n• Product link: " +
        window.location.href + "\n\nPlease confirm availability and delivery. Thank you!";
      waBtn.href = "https://wa.me/923402719595?text=" + encodeURIComponent(msg);
    };
    document.querySelectorAll(".qty-input button").forEach((b) =>
      b.addEventListener("click", () => {
        qty.value = Math.max(1, Math.min(max, getQty() + parseInt(b.dataset.step, 10)));
        updateWaLink();
      })
    );
    qty.addEventListener("input", updateWaLink);
    updateWaLink();
    btn.addEventListener("click", () => {
      addToCart(window.__PRODUCT__, getQty());
      flashMessage("Added to cart ✓");
    });
    const buyBtn = document.getElementById("buyNowBtn");
    if (buyBtn)
      buyBtn.addEventListener("click", () => {
        addToCart(window.__PRODUCT__, getQty());
        window.location.href = "/checkout";
      });
  }
  function flashMessage(msg) {
    const btn = document.getElementById("addToCartBtn");
    if (!btn) return;
    const original = btn.textContent;
    btn.textContent = msg;
    setTimeout(() => (btn.textContent = original), 1400);
  }

  // ---------- Reviews ----------
  function initReviews() {
    const form = document.getElementById("reviewForm");
    if (!form) return;
    const errEl = document.getElementById("reviewError");
    const okEl = document.getElementById("reviewOk");
    const submit = document.getElementById("reviewSubmit");

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      errEl.hidden = true;
      okEl.hidden = true;
      submit.disabled = true;
      submit.textContent = "Posting…";
      const pid = window.__PRODUCT__.id;
      fetch(endpoint("/api/products/" + pid + "/reviews"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: document.getElementById("rAuthor").value.trim(),
          phone: document.getElementById("rPhone").value.trim(),
          rating: document.getElementById("rRating").value,
          title: document.getElementById("rTitle").value.trim(),
          body: document.getElementById("rBody").value.trim(),
        }),
      })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(data.error || "Could not post your review.");
          return data;
        })
        .then((data) => {
          form.reset();
          okEl.textContent = data.verified
            ? "Thanks! Your review is posted and marked as a verified purchase. Reload to see it."
            : "Thanks! Your review has been posted. Reload to see it.";
          okEl.hidden = false;
        })
        .catch((err) => {
          errEl.textContent = err.message;
          errEl.hidden = false;
        })
        .finally(() => {
          submit.disabled = false;
          submit.textContent = "Post Review";
        });
    });
  }

  // ---------- Cart page ----------
  function initCart() {
    const list = document.getElementById("cartList");
    if (!list) return;

    function render() {
      const cart = getCart();
      if (!cart.length) {
        list.innerHTML =
          '<div class="cart-empty">🛒<h3>Your cart is empty</h3><p>Add some products to get started.</p>' +
          '<a class="btn btn-primary" style="margin-top:12px" href="/shop">Browse Products</a></div>';
        document.getElementById("subtotal").textContent = fmt(0);
        document.getElementById("cartTotal").textContent = fmt(0);
        document.getElementById("checkoutBtn").disabled = true;
        return;
      }
      const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
      document.getElementById("subtotal").textContent = fmt(total);
      document.getElementById("cartTotal").textContent = fmt(total);
      document.getElementById("checkoutBtn").disabled = false;
      list.innerHTML = cart
        .map(
          (i) =>
            '<div class="cart-item">' +
            '<img src="' + esc(i.image) + '" alt="">' +
            '<div class="cart-item-body"><div class="name">' + esc(i.name) + "</div>" +
            '<div class="unit">' + fmt(i.price) + " × " + i.quantity + "</div>" +
            '<div class="cart-item-controls">' +
            '<button class="btn-ghost qty-dec" data-id="' + i.id + '">−</button>' +
            "<span>" + i.quantity + "</span>" +
            '<button class="btn-ghost qty-inc" data-id="' + i.id + '">+</button>' +
            '<button class="cart-item-remove" data-id="' + i.id + '">Remove</button>' +
            "</div></div>" +
            '<div class="cart-item-total">' + fmt(i.price * i.quantity) + "</div></div>"
        )
        .join("");

      list.querySelectorAll(".qty-dec").forEach((b) =>
        b.addEventListener("click", () => changeQty(b.dataset.id, -1))
      );
      list.querySelectorAll(".qty-inc").forEach((b) =>
        b.addEventListener("click", () => changeQty(b.dataset.id, 1))
      );
      list.querySelectorAll(".cart-item-remove").forEach((b) =>
        b.addEventListener("click", () => removeItem(b.dataset.id))
      );
    }

    function changeQty(id, delta) {
      const cart = getCart();
      const item = cart.find((i) => i.id == id);
      if (!item) return;
      item.quantity += delta;
      if (item.quantity <= 0) removeItem(id);
      else {
        const maxQ = item.stock || 99;
        if (item.quantity > maxQ) {
          alert("Only " + maxQ + " unit(s) available.");
          item.quantity = maxQ;
        }
        saveCart(cart);
      }
      render();
    }
    function removeItem(id) {
      saveCart(getCart().filter((i) => i.id != id));
      render();
    }

    const checkoutBtn = document.getElementById("checkoutBtn");
    if (checkoutBtn) checkoutBtn.addEventListener("click", () => (window.location.href = "/checkout"));

    render();
  }

  // ---------- Checkout ----------
  function initCheckout() {
    const form = document.getElementById("checkoutForm");
    if (!form) return;
    const itemsList = document.getElementById("checkoutItems");
    const subtotalEl = document.getElementById("checkoutSubtotal");
    const totalEl = document.getElementById("checkoutTotal");
    const discountEl = document.getElementById("checkoutDiscount");
    const discountRow = document.getElementById("discountRow");
    const errEl = document.getElementById("checkoutError");
    const btn = document.getElementById("placeOrderBtn");
    const codeInput = document.getElementById("couponCode");
    const applyBtn = document.getElementById("applyCoupon");
    const msgEl = document.getElementById("couponMsg");
    let discount = 0;

    function showCouponMsg(text, ok) {
      msgEl.textContent = text;
      msgEl.classList.toggle("ok", ok);
      msgEl.hidden = !text;
    }

    function render() {
      const cart = getCart();
      if (!cart.length) {
        itemsList.innerHTML = '<p class="muted" style="padding:10px 0">Your cart is empty.</p>';
        subtotalEl.textContent = fmt(0);
        totalEl.textContent = fmt(0);
        discountRow.hidden = true;
        btn.disabled = true;
        return;
      }
      const subtotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);
      subtotalEl.textContent = fmt(subtotal);
      totalEl.textContent = fmt(subtotal - discount);
      if (discount > 0) {
        discountEl.textContent = "− " + fmt(discount);
        discountRow.hidden = false;
      } else {
        discountRow.hidden = true;
      }
      btn.disabled = false;
      itemsList.innerHTML = cart
        .map(
          (i) =>
            '<div class="mini-item"><img src="' + esc(i.image) + '" alt="">' +
            "<div><strong>" + esc(i.name) + "</strong><span>" + i.quantity + " × " + fmt(i.price) + "</span></div>" +
            "<strong>" + fmt(i.price * i.quantity) + "</strong></div>"
        )
        .join("");
    }

    function validate(code) {
      const subtotal = getCart().reduce((s, i) => s + i.price * i.quantity, 0);
      return fetch(endpoint("/api/coupons/validate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, subtotal: subtotal }),
      })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok || data.valid === false) {
            discount = 0;
            setCoupon(null);
            showCouponMsg(data.error || "This code cannot be applied.", false);
          } else if (data.code) {
            discount = data.discount;
            setCoupon({ code: data.code, discount: discount });
            showCouponMsg(data.message + " You saved " + data.discount_str + ".", true);
          } else {
            discount = 0;
            setCoupon(null);
            showCouponMsg("Enter a discount code.", true);
          }
          render();
        })
        .catch(() => showCouponMsg("Could not check that code. Try again.", false));
    }

    if (codeInput) {
      const saved = getCoupon();
      if (saved && saved.code) {
        codeInput.value = saved.code;
        validate(saved.code);
      }
      if (applyBtn)
        applyBtn.addEventListener("click", () => validate(codeInput.value.trim().toUpperCase()));
      codeInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          validate(codeInput.value.trim().toUpperCase());
        }
      });
    }

    window.addEventListener("cart:updated", render);
    render();

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      errEl.hidden = true;
      const cart = getCart();
      if (!cart.length) return;
      btn.disabled = true;
      btn.textContent = "Placing order…";
      const saved = getCoupon();
      fetch(endpoint("/api/orders"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: document.getElementById("name").value.trim(),
          phone: document.getElementById("phone").value.trim(),
          email: document.getElementById("email").value.trim(),
          city: document.getElementById("city").value.trim(),
          address: document.getElementById("address").value.trim(),
          note: document.getElementById("note").value.trim(),
          coupon_code: codeInput ? codeInput.value.trim().toUpperCase() : "",
          items: cart.map((i) => ({ id: i.id, quantity: i.quantity })),
        }),
      })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(data.error || "Something went wrong. Please try again.");
          localStorage.removeItem(CART_KEY);
          setCoupon(null);
          try {
            localStorage.setItem("ssi_last_order", JSON.stringify({ id: data.order_id, phone: document.getElementById("phone").value.trim() }));
          } catch (err) {}
          updateCartBadge();
          window.location.href = "/order-confirmed/" + data.order_id;
        })
        .catch((err) => {
          errEl.textContent = err.message;
          errEl.hidden = false;
          btn.disabled = false;
          btn.textContent = "Place Order";
        });
    });
  }

  // ---------- Wishlist page ----------
  function initWishlistPage() {
    const grid = document.getElementById("wishlistGrid");
    if (!grid) return;
    const emptyEl = document.getElementById("wishEmpty");
    const labelEl = document.getElementById("wishCountLabel");
    const clearBtn = document.getElementById("wishClear");

    function render() {
      const ids = getWishlist();
      if (labelEl) labelEl.textContent = ids.length + " item" + (ids.length === 1 ? "" : "s") + " saved";
      if (!ids.length) {
        grid.innerHTML = "";
        emptyEl.hidden = false;
        return;
      }
      emptyEl.hidden = true;
      labelEl.textContent = "Loading…";
      fetch(endpoint("/api/products"))
        .then((r) => r.json())
        .then((all) => {
          const wanted = ids.map(Number);
          const list = all.filter((p) => wanted.indexOf(p.id) !== -1);
          const missing = wanted.length - list.length;
          if (!list.length) {
            grid.innerHTML = "";
            emptyEl.hidden = false;
          } else {
            grid.innerHTML = list.map(cardHTML).join("");
          }
          if (labelEl)
            labelEl.textContent =
              list.length + " item" + (list.length === 1 ? "" : "s") + " saved" +
              (missing ? " · " + missing + " no longer available" : "");
        })
        .catch(() => (emptyEl.hidden = false));
    }

    if (clearBtn)
      clearBtn.addEventListener("click", () => {
        if (confirm("Remove all items from your wishlist?")) {
          saveWishlist([]);
          render();
        }
      });
    window.addEventListener("wishlist:updated", render);
    render();
  }

  // ---------- Reorder (order history) ----------
  function initReorder() {
    document.body.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-reorder]");
      if (!btn) return;
      const original = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Adding…";
      fetch(endpoint("/api/orders/reorder"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: btn.dataset.reorder, phone: btn.dataset.phone }),
      })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(data.error || "Could not rebuild your cart.");
          return data;
        })
        .then((data) => {
          const cart = getCart();
          (data.added || []).forEach((item) => {
            const existing = cart.find((i) => i.id === item.id);
            if (existing) existing.quantity = Math.min(existing.quantity + item.quantity, item.stock || 99);
            else cart.push(item);
          });
          saveCart(cart);
          window.location.href = "/cart";
        })
        .catch((err) => {
          alert(err.message);
          btn.disabled = false;
          btn.textContent = original;
        });
    });
  }

  // ---------- Contact ----------
  function initContact() {
    const form = document.getElementById("contactForm");
    if (!form) return;
    const okEl = document.getElementById("contactOk");
    const errEl = document.getElementById("contactError");
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      okEl.hidden = true;
      errEl.hidden = true;
      const body = {
        name: document.getElementById("cname").value.trim(),
        email: document.getElementById("cemail").value.trim(),
        subject: document.getElementById("csubject").value.trim(),
        message: document.getElementById("cmessage").value.trim(),
      };
      fetch(endpoint("/api/contact"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(data.error || "Could not send message.");
          okEl.hidden = false;
          form.reset();
        })
        .catch((err) => {
          errEl.textContent = err.message;
          errEl.hidden = false;
        });
    });
  }

  // ---------- Delegated card buttons ----------
  function initCardButtons() {
    document.body.addEventListener("click", (e) => {
      const wish = e.target.closest("[data-wish]");
      if (wish) {
        e.preventDefault();
        e.stopPropagation();
        toggleWishlist(wish.dataset.wish);
        return;
      }
      const btn = e.target.closest("[data-add]");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      if (btn.disabled) return;
      const product = {
        id: parseInt(btn.dataset.id, 10),
        name: btn.dataset.name,
        price_max: parseInt(btn.dataset.price, 10),
        image: btn.dataset.image,
        category: btn.dataset.category,
        stock: parseInt(btn.dataset.stock, 10),
      };
      addToCart(product, 1);
      btn.textContent = "Added ✓";
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = "Add to Cart";
        btn.disabled = false;
      }, 1200);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    updateCartBadge();
    updateWishlistUI();
    initSearchSuggest();
    initShop();
    initProduct();
    initReviews();
    initCart();
    initCheckout();
    initWishlistPage();
    initReorder();
    initContact();
    initCardButtons();
    initPasswordTools();
  });
})();

/* Show/hide toggle for password fields, and a strength meter on the
   change-password form. Both are pure front-end aids — the server enforces
   the real rules. */
function initPasswordTools() {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-pw-toggle]");
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("data-pw-toggle"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });

  document.addEventListener("input", function (e) {
    if (e.target.id !== "newPassword") return;
    var v = e.target.value;
    var score = 0;
    if (v.length >= 8) score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/[0-9]/.test(v)) score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;
    var bar = document.getElementById("pwStrengthBar");
    var label = document.getElementById("pwStrengthLabel");
    if (!bar || !label) return;
    var words = ["Too short", "Weak", "Fair", "Good", "Strong", "Very strong"];
    var colors = ["#e2e8f0", "#b91c1c", "#b45309", "#a16207", "#15803d", "#15803d"];
    bar.style.width = Math.min(100, (score / 5) * 100) + "%";
    bar.style.background = colors[score];
    label.textContent = v ? words[score] : "";
  });
}
