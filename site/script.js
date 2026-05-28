function card(classes, title, body) {
  const article = document.createElement("article");
  article.className = `card ${classes}`;
  article.innerHTML = `<h2>${title}</h2>${body}`;
  return article;
}

function metricValue(value, suffix = "") {
  return value === null || value === undefined ? "n/a" : `${value}${suffix}`;
}

function createDashboardRenderer(data) {
  const app = document.getElementById("app");
  document.getElementById("body-card").innerHTML = `
    <div class="body-figure">
      <div class="body-head"></div>
      <div class="body-torso"></div>
      <div class="body-arm left"></div>
      <div class="body-arm right"></div>
      <div class="body-leg left"></div>
      <div class="body-leg right"></div>
    </div>
    <h2 class="body-name">${data.body_card.name}</h2>
    <ul class="body-notes">
      ${data.body_card.lines.map((line) => `<li>${line}</li>`).join("")}
    </ul>
  `;

  function statsBlock() {
    const items = [
      ["True 5K", data.headline.true_5k_range, ""],
      ["High Intensity", data.numbers.high_intensity_share_pct, "%"],
      ["Easy-Like Runs", data.numbers.easy_like_share_pct, "%"],
      ["Recent Km", data.numbers.recent_km, " km"],
      ["Avg Steps", data.health.steps?.avg, ""],
      ["Avg Active Kcal", data.health.active_kcal?.avg, ""],
      ["Avg HRV", data.health.hrv?.avg, ""],
      ["Avg RHR", data.health.rhr?.avg, ""],
    ];

    return `
      <div class="stats-grid">
        ${items
          .map(
            ([label, value, suffix]) => `
              <div class="stat">
                <span class="stat-label">${label}</span>
                <span class="stat-value">${metricValue(value, suffix)}</span>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }

  function headlineCard() {
    return card(
      "span-12",
      "Top-Line Read",
      `
        <div class="section-title">
          <p class="muted">${data.meta.watch_note}</p>
        </div>
        ${statsBlock()}
        <div class="pill-row" style="margin-top:16px;">
          ${data.headline.main_limiters.map((item) => `<span class="pill">${item}</span>`).join("")}
        </div>
        <div class="split-layout" style="margin-top:18px;">
          <div>
            <h3>Direct diagnosis</h3>
            <ul class="bullet-list">
              ${data.diagnosis.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
          <div>
            <h3>What stood out</h3>
            <div class="kpi-stack">
              <div class="kpi-line"><span>Best recent 5K</span><strong>${metricValue(data.headline.best_recent_5k.time_min, " min")}</strong></div>
              <div class="kpi-line"><span>Best rolling 5K</span><strong>${metricValue(data.headline.best_rolling_5k.time_min, " min")}</strong></div>
              <div class="kpi-line"><span>Avg weekly distance</span><strong>${metricValue(data.numbers.avg_weekly_km, " km")}</strong></div>
              <div class="kpi-line"><span>Avg weekly run days</span><strong>${metricValue(data.numbers.avg_weekly_run_days, "")}</strong></div>
              <div class="kpi-line"><span>Sub-20 status</span><strong>${data.headline.sub20_status}</strong></div>
            </div>
          </div>
        </div>
      `
    );
  }

  function liveSyncCard(sync) {
    if (!sync) {
      return card(
        "span-12",
        "Live Sync",
        `
          <p class="muted">No live Apple Health sync is connected yet. The dashboard is currently using the processed backend snapshot only.</p>
          <p class="muted">If you want live sync, start the backend in <a href="./HEALTH_SYNC.md">HEALTH_SYNC.md</a> and open the site over <code>http://...:8765</code> instead of <code>file:///...</code>.</p>
        `
      );
    }

    const metrics = sync.metrics || {};
    const pairs = [
      ["Steps", metrics.steps],
      ["Active kcal", metrics.active_kcal],
      ["Resting HR", metrics.resting_hr],
      ["HRV", metrics.hrv],
      ["Sleep", metrics.sleep_hours],
      ["Weight", metrics.body_mass_kg],
      ["VO2max", metrics.vo2max],
    ].filter(([, value]) => value !== undefined);

    return card(
      "span-12",
      "Live Sync",
      `
        <div class="section-title">
          <p class="muted">Latest synced date: ${sync.date || "n/a"} · source: ${sync.source || "unknown"} · bridge write time: ${sync.last_sync_utc || "n/a"}</p>
        </div>
        <div class="stats-grid">
          ${pairs
            .map(
              ([label, value]) => `
                <div class="stat">
                  <span class="stat-label">${label}</span>
                  <span class="stat-value">${value}</span>
                </div>
              `
            )
            .join("")}
        </div>
        ${sync.notes ? `<p class="muted" style="margin-top:14px;">${sync.notes}</p>` : ""}
      `
    );
  }

  function profileCard() {
    return card(
      "span-4",
      "Athlete Profile",
      `
        <div class="kpi-stack">
          <div class="kpi-line"><span>Name</span><strong>${data.profile.name}</strong></div>
          <div class="kpi-line"><span>Age</span><strong>${data.profile.age}</strong></div>
          <div class="kpi-line"><span>Height</span><strong>${data.profile.height_cm} cm</strong></div>
          <div class="kpi-line"><span>Weight range</span><strong>${data.profile.weight_range_kg} kg</strong></div>
        </div>
        <h3 style="margin-top:18px;">Goals</h3>
        <ul class="plain-list">${data.profile.goals.map((item) => `<li>${item}</li>`).join("")}</ul>
        <h3 style="margin-top:18px;">Constraints</h3>
        <ul class="plain-list">${data.profile.constraints.map((item) => `<li>${item}</li>`).join("")}</ul>
      `
    );
  }

  function healthCard() {
    const order = [
      ["steps", "Daily steps"],
      ["active_kcal", "Active calories"],
      ["rhr", "Resting HR"],
      ["hrv", "HRV SDNN"],
      ["vo2max", "VO2max"],
      ["walking_hr", "Walking HR"],
      ["body_mass_kg", "Body mass"],
      ["sleep_hours", "Sleep"],
    ];

    return card(
      "span-8",
      "Apple Health Summary",
      `
        <div class="section-title">
          <p class="muted">Recent recovery window: ${data.meta.analysis_window.recovery_start} to ${data.meta.analysis_window.recovery_end}</p>
        </div>
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Days</th>
              <th>Average</th>
              <th>Latest</th>
              <th>Range</th>
            </tr>
          </thead>
          <tbody>
            ${order
              .filter(([key]) => data.health[key])
              .map(([key, label]) => {
                const metric = data.health[key];
                return `
                  <tr>
                    <td>${label}</td>
                    <td>${metric.days}</td>
                    <td>${metric.avg}</td>
                    <td>${metric.latest}</td>
                    <td>${metric.min} to ${metric.max}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      `
    );
  }

  function constraintsCard() {
    return card(
      "span-4",
      "Next Plan Constraints",
      `
        <ul class="plain-list">${data.next_plan_constraints.map((item) => `<li>${item}</li>`).join("")}</ul>
      `
    );
  }

  function nutritionCard() {
    const n = data.nutrition;
    const f = data.food_focus || {};
    return card(
      "span-8",
      "Calories, Protein, And Food Logs",
      `
        <div class="stats-grid">
          <div class="stat"><span class="stat-label">Estimated BMR</span><span class="stat-value">${n.bmr_estimate}</span></div>
          <div class="stat"><span class="stat-label">Corrected Active Kcal</span><span class="stat-value">${n.active_kcal_corrected_avg}</span></div>
          <div class="stat"><span class="stat-label">Maintenance</span><span class="stat-value">${n.maintenance_kcal_estimate}</span></div>
          <div class="stat"><span class="stat-label">Protein</span><span class="stat-value">${n.protein_g_range[0]}-${n.protein_g_range[1]}g</span></div>
        </div>
        <div class="split-layout" style="margin-top:18px;">
          <div>
            <h3>Daily calorie targets</h3>
            <div class="kpi-stack">
              <div class="kpi-line"><span>Fat-loss range</span><strong>${n.fat_loss_kcal_range[0]}-${n.fat_loss_kcal_range[1]}</strong></div>
              <div class="kpi-line"><span>Easy day</span><strong>${n.easy_day_kcal_range[0]}-${n.easy_day_kcal_range[1]}</strong></div>
              <div class="kpi-line"><span>Long-run day</span><strong>${n.long_run_day_kcal_range[0]}-${n.long_run_day_kcal_range[1]}</strong></div>
              <div class="kpi-line"><span>Fat target</span><strong>${n.fat_g_range[0]}-${n.fat_g_range[1]}g</strong></div>
            </div>
          </div>
          <div>
            <h3>How to use it</h3>
            <ul class="plain-list">${n.carb_guidance.map((item) => `<li>${item}</li>`).join("")}</ul>
            <div style="margin-top:14px;">
              <label class="stat-label" for="calorie-slider">Target Calories</label>
              <input id="calorie-slider" type="range" min="2400" max="3600" step="50" value="${n.fat_loss_kcal_range[1]}" style="width:100%;">
              <p id="slider-output" class="muted" style="margin:8px 0 0;">Target calories: ${n.fat_loss_kcal_range[1]} kcal</p>
            </div>
          </div>
        </div>
        <div class="section-title" style="margin-top:18px;">
          <p class="muted">Food log focus window: ${f.window_start || "n/a"} to ${f.window_end || "n/a"}</p>
        </div>
        <div class="stats-grid">
          <div class="stat"><span class="stat-label">Days Logged</span><span class="stat-value">${metricValue(f.days_logged)}</span></div>
          <div class="stat"><span class="stat-label">Avg Intake</span><span class="stat-value">${metricValue(f.avg?.dietary_kcal, " kcal")}</span></div>
          <div class="stat"><span class="stat-label">Avg Protein</span><span class="stat-value">${metricValue(f.avg?.dietary_protein_g, " g")}</span></div>
          <div class="stat"><span class="stat-label">Protein Hit Rate</span><span class="stat-value">${metricValue(f.protein_hit_rate_pct, "%")}</span></div>
          <div class="stat"><span class="stat-label">Avg Carbs</span><span class="stat-value">${metricValue(f.avg?.dietary_carbs_g, " g")}</span></div>
          <div class="stat"><span class="stat-label">Avg Fat</span><span class="stat-value">${metricValue(f.avg?.dietary_fat_g, " g")}</span></div>
          <div class="stat"><span class="stat-label">Avg Fiber</span><span class="stat-value">${metricValue(f.avg?.dietary_fiber_g, " g")}</span></div>
          <div class="stat"><span class="stat-label">Avg Sodium</span><span class="stat-value">${metricValue(f.avg?.dietary_sodium_mg, " mg")}</span></div>
          <div class="stat"><span class="stat-label">Avg Water</span><span class="stat-value">${metricValue(f.avg?.dietary_water_l, " L")}</span></div>
          <div class="stat"><span class="stat-label">Kcal In Range</span><span class="stat-value">${metricValue(f.kcal_in_range_rate_pct, "%")}</span></div>
        </div>
        ${
          f.recent_days?.length
            ? `
        <table style="margin-top:18px;">
          <thead>
            <tr>
              <th>Date</th>
              <th>Kcal</th>
              <th>Protein</th>
              <th>Carbs</th>
              <th>Fat</th>
            </tr>
          </thead>
          <tbody>
            ${f.recent_days
              .map(
                (day) => `
                  <tr>
                    <td>${day.date}</td>
                    <td>${metricValue(day.kcal)}</td>
                    <td>${metricValue(day.protein_g)}</td>
                    <td>${metricValue(day.carbs_g)}</td>
                    <td>${metricValue(day.fat_g)}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
        `
            : ""
        }
      `
    );
  }

  function oldPlanCard() {
    return card(
      "span-6 old-era",
      "Old Running Plan",
      `
        <p class="muted">Summary of the structured plan you were following before we build the next one.</p>
        <h3>Weekly structure</h3>
        <ul class="plain-list">${data.old_plan.weekly_structure.map((item) => `<li>${item}</li>`).join("")}</ul>
        <h3 style="margin-top:18px;">Definitions</h3>
        <ul class="plain-list">${data.old_plan.definitions.map((item) => `<li>${item}</li>`).join("")}</ul>
      `
    );
  }

  function executionCard() {
    const counts = data.old_plan.execution_counts;
    const tags = Object.entries(counts)
      .map(([key, value]) => {
        const kind = key === "too hard" ? "bad" : key === "ok/mixed" ? "good" : "warn";
        return `<span class="tag ${kind}">${key}: ${value}</span>`;
      })
      .join("");

    return card(
      "span-6 old-era",
      "Plan Vs Actual",
      `
        <p class="muted">The plan said one thing. Your HR and splits often said another.</p>
        <div class="tag-row">${tags}</div>
        <table style="margin-top:16px;">
          <thead>
            <tr>
              <th>Date</th>
              <th>Planned</th>
              <th>Actual</th>
              <th>HR</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody>
            ${data.old_plan.matched_examples
              .map(
                (row) => `
                  <tr>
                    <td>${row.date}</td>
                    <td>${row.planned}</td>
                    <td>${row.actual || "no run"}</td>
                    <td>${metricValue(row.avg_hr, "")}</td>
                    <td>${row.flag}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      `
    );
  }

  function runsCard() {
    return card(
      "span-7",
      "Recent Strava Runs",
      `
        <p class="muted">Recent run window: ${data.meta.analysis_window.runs_start} to ${data.meta.analysis_window.runs_end}</p>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Run</th>
              <th>Km</th>
              <th>Pace</th>
              <th>HR</th>
              <th>Class</th>
            </tr>
          </thead>
          <tbody>
            ${data.run_summary.recent_runs
              .map(
                (row) => `
                  <tr>
                    <td>${row.date}</td>
                    <td>${row.name}</td>
                    <td>${row.distance_km}</td>
                    <td>${row.pace_min_km}</td>
                    <td>${metricValue(row.avg_hr, "")}</td>
                    <td>${row.class}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      `
    );
  }

  function weeklyCard() {
    return card(
      "span-5",
      "Weekly Load",
      `
        <table>
          <thead>
            <tr>
              <th>Week</th>
              <th>Run days</th>
              <th>Runs</th>
              <th>Km</th>
              <th>Minutes</th>
            </tr>
          </thead>
          <tbody>
            ${data.run_summary.weekly
              .map(
                (row) => `
                  <tr>
                    <td>${row.week}</td>
                    <td>${row.run_days}</td>
                    <td>${row.runs}</td>
                    <td>${row.km}</td>
                    <td>${row.minutes}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      `
    );
  }

  function efficiencyCard() {
    return card(
      "span-12",
      "Efficiency And Risk Notes",
      `
        <div class="split-layout">
          <div>
            <h3>Why progress is getting capped</h3>
            <ul class="bullet-list">${data.action_flags.map((item) => `<li>${item}</li>`).join("")}</ul>
          </div>
          <div>
            <h3>Medium run examples</h3>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Run</th>
                  <th>Pace</th>
                  <th>HR</th>
                  <th>Drift</th>
                </tr>
              </thead>
              <tbody>
                ${data.run_summary.efficiency_examples
                  .map(
                    (row) => `
                      <tr>
                        <td>${row.date}</td>
                        <td>${row.name}</td>
                        <td>${row.pace_min_km}</td>
                        <td>${metricValue(row.avg_hr, "")}</td>
                        <td>${metricValue(row.drift, "")}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>
      `
    );
  }

  return {
    render(sync) {
      const section = document.createElement("section");
      section.className = "section-grid";
      section.append(
        headlineCard(),
        liveSyncCard(sync),
        profileCard(),
        constraintsCard(),
        nutritionCard(),
        healthCard(),
        oldPlanCard(),
        executionCard(),
        runsCard(),
        weeklyCard(),
        efficiencyCard()
      );
      app.replaceChildren(section);

      const slider = document.getElementById("calorie-slider");
      const output = document.getElementById("slider-output");
      if (slider && output) {
        slider.addEventListener("input", () => {
          output.textContent = `Target calories: ${slider.value} kcal`;
        });
      }
    },
  };
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} failed`);
  return response.json();
}

async function loadDashboardData() {
  try {
    return await fetchJson("./api/dashboard");
  } catch {
    return window.DASHBOARD_DATA || null;
  }
}

async function loadLiveSync() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    const response = await fetch("./api/live-health", { signal: controller.signal, cache: "no-store" });
    clearTimeout(timeout);
    if (!response.ok) return null;
    const payload = await response.json();
    if (!payload || !payload.metrics || Object.keys(payload.metrics).length === 0) return null;
    return payload;
  } catch {
    return null;
  }
}

(async function init() {
  const data = await loadDashboardData();
  if (!data) {
    document.getElementById("app").innerHTML = `<article class="card span-12"><h2>Dashboard unavailable</h2><p class="muted">Could not load backend dashboard data or the static fallback snapshot.</p></article>`;
    return;
  }
  const sync = await loadLiveSync();
  createDashboardRenderer(data).render(sync);
})();
