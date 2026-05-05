document.addEventListener("DOMContentLoaded", () => {
  const bootstrapAvailable = typeof bootstrap !== "undefined";

  document.querySelectorAll("select.tomselect, select[multiple]").forEach((select) => {
    if (select.tomselect || typeof TomSelect === "undefined") {
      return;
    }
    new TomSelect(select, {
      plugins: select.multiple ? ["remove_button"] : [],
      create: false,
      persist: false,
    });
  });

  const sidebarToggle = document.querySelector("[data-catalog-sidebar-toggle]");
  const sidebarTargetSelector = sidebarToggle?.dataset.catalogSidebarTarget || "#projectFilters";
  const sidebarElement = document.querySelector(sidebarTargetSelector);
  const desktopSidebar = window.matchMedia("(min-width: 992px)");
  const storageKey = "catalogSidebarCollapsed";

  document.querySelectorAll("[data-bs-toggle='dropdown']").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      if (bootstrapAvailable) {
        return;
      }
      event.preventDefault();
      const dropdown = trigger.closest(".dropdown");
      if (!dropdown) {
        return;
      }
      const willOpen = !dropdown.classList.contains("is-open");
      document.querySelectorAll(".dropdown.is-open").forEach((item) => {
        if (item !== dropdown) {
          item.classList.remove("is-open");
        }
      });
      dropdown.classList.toggle("is-open", willOpen);
      trigger.setAttribute("aria-expanded", String(willOpen));
    });
  });

  document.addEventListener("click", (event) => {
    if (!bootstrapAvailable) {
      document.querySelectorAll(".dropdown.is-open").forEach((dropdown) => {
        if (!dropdown.contains(event.target)) {
          dropdown.classList.remove("is-open");
          dropdown.querySelector("[data-bs-toggle='dropdown']")?.setAttribute("aria-expanded", "false");
        }
      });
    }

    if (sidebarElement && sidebarElement.classList.contains("is-open") && sidebarToggle && !sidebarElement.contains(event.target) && !sidebarToggle.contains(event.target)) {
      sidebarElement.classList.remove("is-open");
      sidebarToggle.setAttribute("aria-expanded", "false");
    }
  });

  document.querySelectorAll("[data-bs-dismiss='alert']").forEach((button) => {
    button.addEventListener("click", () => {
      if (bootstrapAvailable) {
        return;
      }
      button.closest(".alert")?.remove();
    });
  });

  const setSidebarToggleState = () => {
    if (!sidebarToggle) {
      return;
    }
    const collapsed = document.body.classList.contains("catalog-sidebar-collapsed");
    sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  };

  if (sidebarToggle) {
    try {
      if (desktopSidebar.matches && window.localStorage.getItem(storageKey) === "1") {
        document.body.classList.add("catalog-sidebar-collapsed");
      }
    } catch (error) {
      // Ignore private browsing or restricted storage.
    }

    setSidebarToggleState();

    sidebarToggle.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        if (!desktopSidebar.matches) {
          if (sidebarElement && bootstrapAvailable) {
            bootstrap.Offcanvas.getOrCreateInstance(sidebarElement).toggle();
          } else if (sidebarElement) {
            const willOpen = !sidebarElement.classList.contains("is-open");
            sidebarElement.classList.toggle("is-open", willOpen);
            sidebarToggle.setAttribute("aria-expanded", String(willOpen));
          }
          return;
        }

        document.body.classList.toggle("catalog-sidebar-collapsed");
        const collapsed = document.body.classList.contains("catalog-sidebar-collapsed");
        try {
          window.localStorage.setItem(storageKey, collapsed ? "1" : "0");
        } catch (error) {
          // Ignore private browsing or restricted storage.
        }
        setSidebarToggleState();
      },
      true,
    );

    desktopSidebar.addEventListener("change", () => {
      if (desktopSidebar.matches && sidebarElement && bootstrapAvailable) {
        bootstrap.Offcanvas.getInstance(sidebarElement)?.hide();
      } else if (desktopSidebar.matches && sidebarElement) {
        sidebarElement.classList.remove("is-open");
      }
      setSidebarToggleState();
    });
  }

  const projectStatus = document.querySelector("[data-project-status]");
  const projectEndDate = document.querySelector("[data-project-end-date]");
  const syncProjectEndDateRequirement = () => {
    if (!projectStatus || !projectEndDate) {
      return;
    }
    projectEndDate.required = ["completed", "archived"].includes(projectStatus.value);
  };

  if (projectStatus && projectEndDate) {
    projectStatus.addEventListener("change", syncProjectEndDateRequirement);
    syncProjectEndDateRequirement();
  }
});
