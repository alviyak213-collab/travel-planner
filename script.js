document.addEventListener('DOMContentLoaded', () => {
  const route = document.getElementById('route');
  document.querySelectorAll('[data-itinerary]').forEach((button) => {
    button.addEventListener('click', async () => {
      const result = document.getElementById(`itinerary-${button.dataset.itinerary}`);
      button.disabled = true;
      button.textContent = 'Generating…';
      try {
        const response = await fetch(`/trip/${button.dataset.itinerary}/itinerary`);
        const suggestion = await response.json();
        if (!response.ok) throw new Error(suggestion.error || 'Unable to generate an itinerary.');
        result.replaceChildren();
        const heading = document.createElement('h4');
        heading.textContent = `${suggestion.trip_days}-day itinerary suggestion`;
        const budget = document.createElement('p');
        budget.textContent = `Budget plan: ${suggestion.budget} total · ${suggestion.per_person} per person · about ${suggestion.daily_budget} per day`;
        const list = document.createElement('ol');
        suggestion.days.forEach((item) => {
          const day = document.createElement('li');
          const title = document.createElement('strong');
          title.textContent = `Day ${item.day}: ${item.title}`;
          day.append(title, document.createTextNode(` — ${item.activity}`));
          list.append(day);
        });
        result.append(heading, budget, list);
        result.hidden = false;
        button.textContent = 'Regenerate itinerary';
      } catch (error) {
        result.textContent = error.message;
        result.hidden = false;
        button.textContent = 'Try again';
      } finally {
        button.disabled = false;
      }
    });
  });

  if (!route) return;

  const status = document.getElementById('status');
  const origin = document.getElementById('origin');
  const destination = document.getElementById('destination');
  const stops = document.getElementById('stops');
  const legs = document.getElementById('legMethods');
  const transport = document.getElementById('transportField');
  const stopsField = document.getElementById('stopsField');
  const startDate = document.getElementById('startDate');
  const endDate = document.getElementById('endDate');
  const upcomingFields = document.getElementById('upcomingFields');
  const budget = document.getElementById('budget');
  const people = document.getElementById('people');
  const interests = document.getElementById('interests');
  const modes = ['Flight', 'Train', 'Car', 'Bus', 'Ship'];

  function renderLegs() {
    const selections = [...legs.querySelectorAll('select')].map((select) => select.value);
    const places = [origin.value, ...stops.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean), destination.value].filter(Boolean);
    legs.innerHTML = places.slice(0, -1).map((from, index) => `<label class="trip-leg"><span>${from} → ${places[index + 1]}</span><select name="leg_transport">${modes.map((mode) => `<option ${selections[index] === mode ? 'selected' : ''}>${mode}</option>`).join('')}</select></label>`).join('');
  }

  function updateRoute() {
    const hasStops = route.value === 'stops';
    stopsField.hidden = !hasStops;
    legs.hidden = !hasStops;
    transport.hidden = hasStops;
    if (hasStops) renderLegs();
  }

  function updateDates() {
    const today = new Date().toLocaleDateString('en-CA');
    startDate.min = endDate.min = startDate.max = endDate.max = '';
    if (status.value === 'upcoming') startDate.min = endDate.min = today;
    else startDate.max = endDate.max = today;
    if (startDate.value) endDate.min = startDate.value;
  }

  function updateUpcomingFields() {
    const isUpcoming = status.value === 'upcoming';
    upcomingFields.hidden = !isUpcoming;
    [budget, people, interests].forEach((field) => field.required = isUpcoming);
  }

  route.onchange = updateRoute;
  status.onchange = () => { updateDates(); updateUpcomingFields(); };
  startDate.onchange = updateDates;
  [origin, destination, stops].forEach((input) => input.oninput = () => route.value === 'stops' && renderLegs());
  updateRoute();
  updateDates();
  updateUpcomingFields();
});
