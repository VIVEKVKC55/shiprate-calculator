(() => {
  const form = document.getElementById("calculator-form");
  if (form) {
    const button = document.getElementById("submit-button");
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      } else {
        button.disabled = true;
        button.querySelector(".button-label").classList.add("d-none");
        button.querySelector(".spinner-border").classList.remove("d-none");
      }
      form.classList.add("was-validated");
    });
    form.addEventListener("reset", () => {
      form.classList.remove("was-validated");
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
    }
    form.elements.namedItem("weight").min = "0.001";
    form.elements.namedItem("weight").required = true;
    form.elements.namedItem("order_value").min = "0";
    form.elements.namedItem("order_value").required = true;
  }

  const sortButton = document.getElementById("sort-rate");
  if (sortButton) {
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
