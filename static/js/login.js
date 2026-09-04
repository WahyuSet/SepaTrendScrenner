// ==============================================================================
// TIREXXZ SCRENNER - ENTERPRISE LOGIN CONTROLLER
// ==============================================================================

function togglePasswordVisibility() {
  const passwordInput = document.getElementById("password");
  const toggleBtn = document.getElementById("btn-toggle-password");
  
  if (passwordInput.type === "password") {
    passwordInput.type = "text";
    toggleBtn.textContent = "🙈";
  } else {
    passwordInput.type = "password";
    toggleBtn.textContent = "👁️";
  }
}

function showAlert(message, isWarning = false) {
  const alertEl = document.getElementById("login-alert");
  const msgEl = document.getElementById("alert-message");
  const iconEl = document.getElementById("alert-icon");

  msgEl.textContent = message;
  iconEl.textContent = isWarning ? "⏳" : "⚠️";

  alertEl.classList.remove("hidden");
  alertEl.classList.remove("shake");
  
  // Trigger DOM reflow to restart CSS shake animation
  void alertEl.offsetWidth;
  alertEl.classList.add("shake");
}

function hideAlert() {
  const alertEl = document.getElementById("login-alert");
  if (alertEl) alertEl.classList.add("hidden");
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  hideAlert();

  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const rememberCheckbox = document.getElementById("remember");
  const submitBtn = document.getElementById("btn-login-submit");
  const btnText = submitBtn.querySelector(".btn-text");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const remember = rememberCheckbox.checked;

  // 1. Client-Side Validation
  if (!username) {
    showAlert("Silakan masukkan username admin.");
    usernameInput.focus();
    return;
  }
  if (!password) {
    showAlert("Silakan masukkan password admin.");
    passwordInput.focus();
    return;
  }

  // 2. Set Loading State
  submitBtn.disabled = true;
  btnText.textContent = "Memverifikasi...";
  btnSpinner.classList.remove("hidden");

  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest"
      },
      body: JSON.stringify({
        username: username,
        password: password,
        remember: remember
      })
    });

    const result = await response.json();

    if (response.ok && result.status === "success") {
      btnText.textContent = "Berhasil! Mengalihkan...";
      // Redirect to next target or main dashboard
      const urlParams = new URLSearchParams(window.location.search);
      const nextUrl = urlParams.get("next") || result.redirect || "/";
      window.location.href = nextUrl;
    } else {
      // Show failure alert
      showAlert(result.message || "Kredensial tidak valid.");
      submitBtn.disabled = false;
      btnText.textContent = "Masuk ke Workstation";
      btnSpinner.classList.add("hidden");
      passwordInput.value = "";
      passwordInput.focus();
    }
  } catch (err) {
    console.error("Login fetch error:", err);
    showAlert("Terjadi kesalahan jaringan atau server tidak merespons.");
    submitBtn.disabled = false;
    btnText.textContent = "Masuk ke Workstation";
    btnSpinner.classList.add("hidden");
  }
}
