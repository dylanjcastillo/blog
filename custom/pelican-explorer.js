document.addEventListener("DOMContentLoaded", function () {
  const containers = document.querySelectorAll(".pelican-explorer");

  containers.forEach((container) => {
    let config;
    try {
      config = JSON.parse(container.dataset.config);
    } catch (e) {
      console.error("Invalid JSON in data-config:", e);
      return;
    }

    const { base, models, animals, vehicles, samples } = config;
    const state = { model: models[0].slug, sample: 0 };
    let scores = {};

    const controls = document.createElement("div");
    controls.className = "pe-controls";

    const makeSelect = (options, initial, label, onChange) => {
      const wrapper = document.createElement("label");
      wrapper.className = "pe-select-wrapper";
      const span = document.createElement("span");
      span.textContent = label;
      const select = document.createElement("select");
      options.forEach((opt) => {
        const o = document.createElement("option");
        o.value = String(opt.value);
        o.textContent = opt.label;
        if (String(opt.value) === String(initial)) o.selected = true;
        select.appendChild(o);
      });
      select.addEventListener("change", () => {
        onChange(select.value);
        render();
      });
      wrapper.appendChild(span);
      wrapper.appendChild(select);
      controls.appendChild(wrapper);
    };

    makeSelect(
      models.map((m) => ({ value: m.slug, label: m.name })),
      state.model, "Lab", (v) => (state.model = v)
    );
    makeSelect(
      Array.from({ length: samples }, (_, i) => ({ value: i, label: `${i + 1} of ${samples}` })),
      state.sample, "Sample", (v) => (state.sample = Number(v))
    );

    const grid = document.createElement("div");
    grid.className = "pe-grid";

    container.appendChild(controls);
    container.appendChild(grid);

    fetch(`${base}/scores.json`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => {
        scores = data;
        render();
      })
      .catch(() => {});

    const promptId = (animal, vehicle) => `${animal}-${vehicle}`.replace(/ /g, "-");

    function render() {
      const model = models.find((m) => m.slug === state.model);
      grid.innerHTML = "";

      animals.forEach((animal) => {
        const card = document.createElement("div");
        card.className = "pe-card";

        const title = document.createElement("div");
        title.className = "pe-card-title";
        title.textContent = animal;
        card.appendChild(title);

        const row = document.createElement("div");
        row.className = "pe-card-row";

        vehicles.forEach((vehicle) => {
          const pid = promptId(animal, vehicle);
          const url = `${base}/${state.model}/${pid}__s${state.sample}.png`;
          const cell = document.createElement("div");
          cell.className = "pe-cell";

          const labelDiv = document.createElement("div");
          labelDiv.className = "pe-cell-label";
          labelDiv.textContent = vehicle;
          cell.appendChild(labelDiv);

          const img = document.createElement("img");
          img.src = url;
          img.loading = "lazy";
          img.alt = `${model.name}: ${animal} + ${vehicle}, sample ${state.sample + 1}`;
          img.addEventListener("click", () => window.open(url, "_blank"));
          img.addEventListener("error", () => {
            const failed = document.createElement("div");
            failed.className = "pe-failed";
            failed.textContent = "failed";
            cell.replaceChild(failed, img);
          });
          cell.appendChild(img);

          const sc = ((scores[state.model] || {})[pid] || {})[String(state.sample)];
          if (sc && sc.a != null) {
            const badge = document.createElement("div");
            badge.className = "pe-score";
            badge.textContent = `A${Math.round(sc.a)} · V${Math.round(sc.v)} · C${Math.round(sc.c)}`;
            badge.title = `animal ${sc.a} · vehicle ${sc.v} · action ${sc.c} (out of 5)`;
            cell.appendChild(badge);
          }

          row.appendChild(cell);
        });

        card.appendChild(row);
        grid.appendChild(card);
      });
    }

    render();
  });
});
