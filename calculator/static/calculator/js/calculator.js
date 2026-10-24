(() => {
  const form = document.getElementById("calculator-form");
  if (form) {
    const button = document.getElementById("submit-button");
    const results = document.getElementById("async-results");
    const status = document.getElementById("calculator-status");
    const courierResults = document.getElementById("courier-results");
    const locationLookups = {};

    const clearFieldErrors = () => {
      form.querySelectorAll(".ajax-field-error").forEach((node) => node.remove());
      form.querySelectorAll(".is-invalid").forEach((field) => field.classList.remove("is-invalid"));
    };

    const showStatus = (message, kind) => {
      results.classList.remove("d-none");
      results.setAttribute("aria-busy", kind === "info" ? "true" : "false");
      status.className = `alert alert-${kind} async-status`;
      status.textContent = message;
      status.classList.toggle("d-none", !message);
    };

    const addCell = (row, value, className = "") => {
      const cell = document.createElement("td");
      if (className) cell.className = className;
      cell.textContent = value;
      row.appendChild(cell);
      return cell;
    };

    const renderCouriers = (couriers, shipment) => {
      courierResults.replaceChildren();
      if (!couriers.length) {
        const empty = document.createElement("section");
        empty.className = "surface-card empty-state async-empty";
        const title = document.createElement("h2");
        title.textContent = "No serviceable couriers";
        const copy = document.createElement("p");
        copy.textContent = "Shiprocket returned no courier options for this route and shipment. Check the details and try again.";
        empty.append(title, copy);
        courierResults.appendChild(empty);
        return;
      }

      const card = document.createElement("section");
      card.className = "surface-card results-card async-card";
      const heading = document.createElement("div");
      heading.className = "card-heading";
      const headingCopy = document.createElement("div");
      const title = document.createElement("h2");
      title.textContent = `Available couriers (${couriers.length})`;
      const subtitle = document.createElement("p");
      subtitle.textContent = `Shiprocket estimates for ${shipment.pickup_postcode} → ${shipment.delivery_postcode}, ${shipment.weight} kg, ${shipment.payment_mode.toUpperCase()}.`;
      headingCopy.append(title, subtitle);
      const estimate = document.createElement("span");
      estimate.className = "estimate-label";
      estimate.textContent = "ESTIMATES";
      heading.append(headingCopy, estimate);

      const wrapper = document.createElement("div");
      wrapper.className = "table-responsive";
      const table = document.createElement("table");
      table.className = "table courier-table";
      table.innerHTML = "<thead><tr><th>Courier service</th><th>Estimated delivery</th><th>COD</th><th class=\"text-end\"><button type=\"button\" class=\"sort-button\" aria-label=\"Sort by shipping rate\">Estimated rate ↕</button></th></tr></thead><tbody></tbody>";
      const body = table.querySelector("tbody");
      couriers.forEach((courier) => {
        const row = document.createElement("tr");
        const courierName = document.createElement("strong");
        courierName.textContent = courier.courier_name || "Courier option";
        const nameCell = document.createElement("td");
        nameCell.appendChild(courierName);
        row.appendChild(nameCell);
        addCell(row, courier.etd || (courier.estimated_delivery_days ? `${courier.estimated_delivery_days} days` : "Not provided"));
        addCell(row, courier.cod === undefined ? "Not provided" : (courier.cod ? "Available" : "Unavailable"));
        const rate = courier.rate;
        const rateCell = addCell(row, rate === undefined ? "Not provided" : `₹${rate}`, "text-end rate-cell");
        rateCell.dataset.rate = rate === undefined ? "" : String(rate);
        body.appendChild(row);
      });
      const disclaimer = document.createElement("p");
      disclaimer.className = "disclaimer";
      disclaimer.textContent = "Rates are estimates. Final shipping costs may differ due to shipment characteristics, surcharges, account configuration, and other applicable charges.";
      wrapper.appendChild(table);
      card.append(heading, wrapper, disclaimer);
      courierResults.appendChild(card);
      attachRateSorting(table);
    };

    const attachRateSorting = (table) => {
      const sortButton = table.querySelector(".sort-button");
      let ascending = true;
      sortButton.addEventListener("click", () => {
        const body = table.querySelector("tbody");
        const rows = [...body.rows];
        rows.sort((a, b) => {
          const left = Number(a.querySelector(".rate-cell").dataset.rate);
          const right = Number(b.querySelector(".rate-cell").dataset.rate);
          const leftMissing = !Number.isFinite(left);
          const rightMissing = !Number.isFinite(right);
          if (leftMissing || rightMissing) return leftMissing === rightMissing ? 0 : leftMissing ? 1 : -1;
          return ascending ? left - right : right - left;
        });
        rows.forEach((row) => body.appendChild(row));
        ascending = !ascending;
        sortButton.textContent = `Estimated rate ${ascending ? "↑" : "↓"}`;
      });
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFieldErrors();
      courierResults.replaceChildren();
      if (!form.checkValidity()) {
        form.classList.add("was-validated");
        form.reportValidity();
        return;
      }

      const shipment = Object.fromEntries(new FormData(form).entries());
      button.disabled = true;
      button.querySelector(".button-label").classList.add("d-none");
      button.querySelector(".spinner-border").classList.remove("d-none");
      showStatus("Checking live courier availability and rates…", "info");

      try {
        const response = await fetch(form.action || window.location.href, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
          credentials: "same-origin",
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          if (payload.errors) {
            for (const [name, errors] of Object.entries(payload.errors)) {
              const field = form.elements.namedItem(name);
              if (!field || !errors.length) continue;
              const input = field.length && !field.tagName ? field[0] : field;
              input.classList.add("is-invalid");
              const feedback = document.createElement("div");
              feedback.className = "invalid-feedback d-block ajax-field-error";
              feedback.textContent = errors.map((error) => error.message).join(" ");
              (input.closest(".col-md-6, .col-12, .col-4") || input.parentElement).appendChild(feedback);
            }
            showStatus("Please check the highlighted fields and try again.", "warning");
          } else {
            showStatus(payload.error || "We couldn’t calculate rates right now. Please try again.", "warning");
          }
          return;
        }
        status.classList.add("d-none");
        status.textContent = "";
        renderCouriers(payload.couriers || [], shipment);
      } catch (error) {
        showStatus("A connection issue prevented the rate lookup. Please try again.", "danger");
      } finally {
        button.disabled = false;
        button.querySelector(".button-label").classList.remove("d-none");
        button.querySelector(".spinner-border").classList.add("d-none");
        results.setAttribute("aria-busy", "false");
      }
    });

    form.addEventListener("reset", () => {
      form.classList.remove("was-validated");
      clearFieldErrors();
      results.classList.add("d-none");
      courierResults.replaceChildren();
      status.textContent = "";
      for (const name of ["pickup_postcode", "delivery_postcode"]) {
        const location = document.getElementById(`${name === "pickup_postcode" ? "pickup" : "delivery"}-location`);
        location.textContent = "";
        location.classList.remove("is-loading", "is-error");
        if (locationLookups[name]) clearTimeout(locationLookups[name].timer);
        if (locationLookups[name]?.controller) locationLookups[name].controller.abort();
        delete locationLookups[name];
      }
      button.disabled = false;
      button.querySelector(".button-label").classList.remove("d-none");
      button.querySelector(".spinner-border").classList.add("d-none");
    });

    for (const name of ["pickup_postcode", "delivery_postcode"]) {
      const input = form.elements.namedItem(name);
      input.inputMode = "numeric";
      input.pattern = "[0-9]{6}";
      input.maxLength = 6;
      input.required = true;
      input.title = "Enter a six-digit Indian pincode.";
      const prefix = name === "pickup_postcode" ? "pickup" : "delivery";
      const location = document.getElementById(`${prefix}-location`);
      const lookupLocation = () => {
        if (locationLookups[name]?.timer) clearTimeout(locationLookups[name].timer);
        if (locationLookups[name]?.controller) locationLookups[name].controller.abort();
        location.textContent = "";
        location.classList.remove("is-error", "is-loading");
        if (!/^[1-9][0-9]{5}$/.test(input.value)) return;
        location.classList.add("is-loading");
        location.textContent = "Finding city…";
        const controller = new AbortController();
        const timer = setTimeout(async () => {
          try {
            const lookupUrl = location.dataset.lookupUrl.replace("000000", encodeURIComponent(input.value));
            const response = await fetch(lookupUrl, {
              headers: { Accept: "application/json" },
              credentials: "same-origin",
              signal: controller.signal,
            });
            const payload = await response.json();
            if (input.value.length !== 6) {
              return;
            }
            if (!response.ok || !payload.ok) {
              location.textContent = response.status === 404 ? "No city found for this pincode." : "City lookup is temporarily unavailable.";
              location.classList.add("is-error");
              return;
            }
            location.textContent = [payload.city, payload.state].filter(Boolean).join(", ");
          } catch (error) {
            if (error.name !== "AbortError") {
              location.textContent = "City lookup is temporarily unavailable.";
              location.classList.add("is-error");
            }
          } finally {
            if (locationLookups[name]?.controller === controller) {
              location.classList.remove("is-loading");
              delete locationLookups[name];
            }
          }
        }, 250);
        locationLookups[name] = { timer, controller };
      };
      input.addEventListener("input", lookupLocation);
      input.addEventListener("change", lookupLocation);
      if (input.value.length === 6) lookupLocation();
    }
    form.elements.namedItem("weight").min = "0.001";
    form.elements.namedItem("weight").required = true;
    form.elements.namedItem("order_value").min = "0";
    form.elements.namedItem("order_value").required = true;
  }

  const existingSortButton = document.getElementById("sort-rate");
  if (existingSortButton) attachStandaloneSorting(existingSortButton);

  function attachStandaloneSorting(sortButton) {
    let ascending = true;
    sortButton.addEventListener("click", () => {
      const body = document.querySelector("#courier-table tbody");
      const rows = [...body.rows];
      rows.sort((a, b) => {
        const left = Number(a.querySelector(".rate-cell").dataset.rate);
        const right = Number(b.querySelector(".rate-cell").dataset.rate);
        const leftMissing = !Number.isFinite(left);
        const rightMissing = !Number.isFinite(right);
        if (leftMissing || rightMissing) return leftMissing === rightMissing ? 0 : leftMissing ? 1 : -1;
        return ascending ? left - right : right - left;
      });
      rows.forEach((row) => body.appendChild(row));
      ascending = !ascending;
      sortButton.textContent = `Estimated rate ${ascending ? "↑" : "↓"}`;
    });
  }
})();
