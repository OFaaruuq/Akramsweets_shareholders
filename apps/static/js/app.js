/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Main Js File
*/

class App {
  constructor() {
    // Cache frequently used selectors
    this.body = document.body;
    this.docEl = document.documentElement;
    this.toastPlacement = document.getElementById("toastPlacement");
    this.toastSelector = document.getElementById("selectToastPlacement");
    this.alertPlaceholder = document.getElementById("liveAlertPlaceholder");
    this.alertTrigger = document.getElementById("liveAlertBtn");
    this.menuToggleBtn = document.querySelector(".button-toggle-menu");
    this.sideMenu = document.getElementById("side-menu");

    // Handlers for cleanup
    this._handlers = [];
  }

  initComponents() {
    Waves.init();
    feather.replace();

    document.querySelectorAll('[data-bs-toggle="popover"]').forEach((el) => new bootstrap.Popover(el));
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
    document.querySelectorAll(".toast").forEach((el) => new bootstrap.Toast(el));

    if (this.toastPlacement && this.toastSelector) {
      const changeHandler = (e) => {
        if (!this.toastPlacement.dataset.originalClass) {
          this.toastPlacement.dataset.originalClass = this.toastPlacement.className;
        }
        this.toastPlacement.className = `${this.toastPlacement.dataset.originalClass} ${e.target.value}`;
      };
      this.toastSelector.addEventListener("change", changeHandler);
      this._handlers.push(() => this.toastSelector.removeEventListener("change", changeHandler));
    }

    if (this.alertTrigger && this.alertPlaceholder) {
      const clickHandler = () => {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = `<div class="alert alert-primary alert-dismissible" role="alert">
          Nice, you triggered this alert message!
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;
        this.alertPlaceholder.append(wrapper);
      };
      this.alertTrigger.addEventListener("click", clickHandler);
      this._handlers.push(() => this.alertTrigger.removeEventListener("click", clickHandler));
    }
  }

  initControls() {
    const fullscreenToggles = document.querySelectorAll('[data-toggle="fullscreen"]');

    const clickHandler = (e) => {
      e.preventDefault();
      this.body.classList.toggle("fullscreen-enable");

      if (!document.fullscreenElement && !document.mozFullScreenElement && !document.webkitFullscreenElement) {
        if (this.docEl.requestFullscreen) this.docEl.requestFullscreen();
        else if (this.docEl.mozRequestFullScreen) this.docEl.mozRequestFullScreen();
        else if (this.docEl.webkitRequestFullscreen) this.docEl.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
      } else {
        if (document.cancelFullScreen) document.cancelFullScreen();
        else if (document.mozCancelFullScreen) document.mozCancelFullScreen();
        else if (document.webkitCancelFullScreen) document.webkitCancelFullScreen();
      }
    };

    fullscreenToggles.forEach((el) => {
      el.addEventListener("click", clickHandler);
      this._handlers.push(() => el.removeEventListener("click", clickHandler));
    });

    const exitHandler = () => {
      if (!document.webkitIsFullScreen && !document.mozFullScreen && !document.msFullscreenElement) {
        this.body.classList.remove("fullscreen-enable");
      }
    };

    document.addEventListener("fullscreenchange", exitHandler);
    document.addEventListener("webkitfullscreenchange", exitHandler);
    document.addEventListener("mozfullscreenchange", exitHandler);

    this._handlers.push(() => document.removeEventListener("fullscreenchange", exitHandler));
    this._handlers.push(() => document.removeEventListener("webkitfullscreenchange", exitHandler));
    this._handlers.push(() => document.removeEventListener("mozfullscreenchange", exitHandler));
  }

  initMenu() {
    if (this.menuToggleBtn) {
      const toggleHandler = () => {
        const current = this.body.getAttribute("data-sidebar");
        this.body.setAttribute("data-sidebar", current === "default" ? "hidden" : "default");
      };
      this.menuToggleBtn.addEventListener("click", toggleHandler);
      this._handlers.push(() => this.menuToggleBtn.removeEventListener("click", toggleHandler));
    }

    const resizeHandler = () => {
      this.body.setAttribute("data-sidebar", window.innerWidth < 1040 ? "hidden" : "default");
    };
    window.addEventListener("resize", resizeHandler);
    this._handlers.push(() => window.removeEventListener("resize", resizeHandler));
    resizeHandler();

    if (!this.sideMenu) return;

    const collapseElements = this.sideMenu.querySelectorAll("li .collapse");
    collapseElements.forEach((collapse) => {
      const showHandler = (event) => {
        const current = event.target.closest(".collapse.show");
        this.sideMenu.querySelectorAll(".collapse.show").forEach((el) => {
          if (el !== current) new bootstrap.Collapse(el, { toggle: false }).hide();
        });
      };
      collapse.addEventListener("show.bs.collapse", showHandler);
      this._handlers.push(() => collapse.removeEventListener("show.bs.collapse", showHandler));
    });

    const currentPage = window.location.href.split(/[?#]/)[0];
    const links = this.sideMenu.querySelectorAll("a");

    links.forEach((link) => {
      if (link.href === currentPage) {
        link.classList.add("active");
        let el = link.parentElement;
        for (let i = 0; i < 6 && el && el !== document.body; i++) {
          el.classList.add("menuitem-active");
          if (el.classList.contains("collapse")) el.classList.add("show");
          el = el.parentElement;
        }
      }
    });
  }

  destroy() {
    this._handlers.forEach((unbind) => unbind());
    this._handlers = [];
  }

  init() {
    this.initComponents();
    this.initControls();
    this.initMenu();
  }
}

// Instantiate
const appInstance = new App();
appInstance.init();