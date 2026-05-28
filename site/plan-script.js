async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} failed`);
  return response.json();
}

async function loadPlanSchedule() {
  try {
    return await fetchJson("./api/plan/schedule");
  } catch {
    return window.PLAN_SCHEDULE || [];
  }
}

(async function init() {
  const planSchedule = await loadPlanSchedule();
  const scheduleByDate = new Map(planSchedule.map((entry) => [entry.date, entry]));
  const datePicker = document.getElementById("plan-date-picker");
  const selectedWorkout = document.getElementById("selected-workout");
  const tableBody = document.getElementById("plan-table-body");
  const prevButton = document.getElementById("prev-day");
  const nextButton = document.getElementById("next-day");
  const jumpTodayButton = document.getElementById("jump-today");

  function formatPrettyDate(dateString) {
    const date = new Date(`${dateString}T12:00:00`);
    return date.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }

  function todayIsoLocal() {
    const now = new Date();
    const tz = now.getTimezoneOffset();
    const local = new Date(now.getTime() - tz * 60000);
    return local.toISOString().slice(0, 10);
  }

  function clampDate(dateString) {
    if (!planSchedule.length) return "";
    if (dateString < planSchedule[0].date) return planSchedule[0].date;
    if (dateString > planSchedule[planSchedule.length - 1].date) return planSchedule[planSchedule.length - 1].date;
    return dateString;
  }

  function renderSelected(dateString) {
    const entry = scheduleByDate.get(dateString);
    if (!entry) return;
    const currentDay = todayIsoLocal();
    let status = "Selected workout";
    if (dateString === currentDay) {
      status = "Current day workout";
    } else if (currentDay < planSchedule[0].date && dateString === planSchedule[0].date) {
      status = "Next scheduled workout";
    } else if (currentDay > planSchedule[planSchedule.length - 1].date && dateString === planSchedule[planSchedule.length - 1].date) {
      status = "Final scheduled workout";
    }

    selectedWorkout.innerHTML = `
      <div class="selected-header">
        <div>
          <p class="eyebrow" style="margin-bottom:8px;">${status}</p>
          <h3 class="selected-title">${formatPrettyDate(entry.date)}</h3>
          <p class="muted" style="margin:8px 0 0;">${entry.category}</p>
        </div>
        <div class="selected-pills">
          <span class="pill">${entry.duration}</span>
          <span class="pill">${entry.target_pace}</span>
          <span class="pill">${entry.target_hr}</span>
        </div>
      </div>
      <div class="selected-grid">
        <div class="selected-card">
          <h4>Exact session</h4>
          <p>${entry.details}</p>
        </div>
        <div class="selected-card">
          <h4>Notes</h4>
          <p>${entry.notes}</p>
        </div>
      </div>
    `;
  }

  function renderTable() {
    tableBody.innerHTML = planSchedule
      .map(
        (entry) => `
          <tr data-date="${entry.date}">
            <td>${entry.date}</td>
            <td>${entry.day}</td>
            <td>${entry.category}</td>
            <td>${entry.duration}</td>
            <td>${entry.target_pace}</td>
            <td>${entry.target_hr}</td>
            <td>${entry.details}<br><span class="muted">${entry.notes}</span></td>
          </tr>
        `
      )
      .join("");

    [...tableBody.querySelectorAll("tr")].forEach((row) => {
      row.addEventListener("click", () => {
        const nextDate = row.getAttribute("data-date");
        datePicker.value = nextDate;
        renderSelected(nextDate);
        highlightRow(nextDate);
      });
    });
  }

  function highlightRow(dateString) {
    [...tableBody.querySelectorAll("tr")].forEach((row) => {
      row.classList.toggle("active-row", row.getAttribute("data-date") === dateString);
    });
  }

  function moveDay(step) {
    const currentIndex = planSchedule.findIndex((entry) => entry.date === datePicker.value);
    if (currentIndex < 0) return;
    const nextIndex = Math.max(0, Math.min(planSchedule.length - 1, currentIndex + step));
    const nextDate = planSchedule[nextIndex].date;
    datePicker.value = nextDate;
    renderSelected(nextDate);
    highlightRow(nextDate);
  }

  renderTable();
  const initialDate = clampDate(todayIsoLocal());
  datePicker.value = scheduleByDate.has(initialDate) ? initialDate : planSchedule[0]?.date || "";
  renderSelected(datePicker.value);
  highlightRow(datePicker.value);

  datePicker.addEventListener("input", () => {
    const nextDate = clampDate(datePicker.value);
    datePicker.value = nextDate;
    renderSelected(nextDate);
    highlightRow(nextDate);
  });

  prevButton.addEventListener("click", () => moveDay(-1));
  nextButton.addEventListener("click", () => moveDay(1));
  jumpTodayButton.addEventListener("click", () => {
    const nextDate = clampDate(todayIsoLocal());
    datePicker.value = nextDate;
    renderSelected(nextDate);
    highlightRow(nextDate);
  });
})();
