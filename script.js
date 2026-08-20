const STORAGE_KEY = 'travelmate-users';
const SESSION_KEY = 'travelmate-session';
const MODES = ['Flight', 'Train', 'Car', 'Bus', 'Ship'];

function readUsers() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
}

function saveUsers(users) { localStorage.setItem(STORAGE_KEY, JSON.stringify(users)); }
function currentUser() { return readUsers().find((user) => user.email === localStorage.getItem(SESSION_KEY)); }

function showMessage(text, success = false) {
  const message = document.getElementById('authMessage');
  if (!message) return;
  message.textContent = text;
  message.className = `message${success ? ' success' : ''}`;
}

function tripDays(start, end) {
  return Math.round((new Date(`${end}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000) + 1;
}

function itineraryFor(trip) {
  const interests = trip.interests.split(',').map((item) => item.trim()).filter(Boolean);
  const activities = {
    food: 'Visit a local food market and choose a regional speciality.',
    beach: 'Spend the afternoon at a beach or waterfront, with time for a sunset walk.',
    museum: 'Book a museum or heritage-site visit and explore the surrounding area.',
    history: "Take a guided heritage walk through the city's historic district.",
    art: 'Explore a local gallery, creative neighbourhood, or public-art trail.',
    nature: 'Plan a park, garden, or scenic day trip with a relaxed outdoor lunch.',
    adventure: 'Choose an active experience, such as a hike, bike tour, or water activity.'
  };
  const matchingActivities = Object.entries(activities)
    .filter(([keyword]) => interests.some((interest) => interest.toLowerCase().includes(keyword)))
    .map(([, activity]) => activity);
  const days = tripDays(trip.start_date, trip.end_date);
  return Array.from({ length: days }, (_, index) => {
    if (index === 0) return { day: 1, title: 'Arrival and neighbourhood discovery', activity: 'Arrive, check in, and take an easy orientation walk near your stay.' };
    if (index === days - 1) return { day: days, title: 'Easy finale and departure', activity: 'Enjoy a relaxed breakfast, revisit a favourite spot, and leave time for departure.' };
    return { day: index + 1, title: `${interests[(index - 1) % interests.length] || 'Local'} day`, activity: matchingActivities[(index - 1) % matchingActivities.length] || 'Explore a walkable neighbourhood, sample local food, and save time for an unplanned discovery.' };
  });
}

function bindAuth() {
  const login = document.getElementById('loginForm');
  const register = document.getElementById('registerForm');
  if (login) login.onsubmit = (event) => {
    event.preventDefault();
    const email = login.loginEmail.value.trim().toLowerCase();
    const user = readUsers().find((item) => item.email === email && item.password === login.loginPassword.value);
    if (!user) return showMessage('Invalid email or password.');
    localStorage.setItem(SESSION_KEY, email);
    window.location.href = 'dashboard.html';
  };
  if (register) register.onsubmit = (event) => {
    event.preventDefault();
    const name = register.registerName.value.trim();
    const email = register.registerEmail.value.trim().toLowerCase();
    const password = register.registerPassword.value;
    if (!name || password.length < 6) return showMessage('Enter a name and a password of at least 6 characters.');
    if (password !== register.confirmPassword.value) return showMessage('Passwords do not match.');
    const users = readUsers();
    if (users.some((item) => item.email === email)) return showMessage('This email is already registered.');
    users.push({ name, email, password, trips: [] });
    saveUsers(users);
    register.reset();
    showMessage('Registration successful. Please log in.', true);
  };
}

function updateAccount(account) { saveUsers(readUsers().map((item) => item.email === account.email ? account : item)); }

function renderLegs() {
  const form = document.getElementById('tripForm');
  if (form.tripRoute.value !== 'stops') return;
  const places = [form.tripOrigin.value, ...form.tripStops.value.split(/\n|,/), form.tripDestination.value].map((place) => place.trim()).filter(Boolean);
  document.getElementById('tripLegs').replaceChildren(...places.slice(0, -1).map((place, index) => {
    const label = document.createElement('label');
    label.className = 'trip-leg';
    const text = document.createElement('span');
    text.textContent = `${place} → ${places[index + 1]}`;
    const select = document.createElement('select');
    select.name = 'leg_transport';
    MODES.forEach((mode) => select.add(new Option(mode, mode)));
    label.append(text, select);
    return label;
  }));
}

function updateTripFields() {
  const form = document.getElementById('tripForm');
  const hasStops = form.tripRoute.value === 'stops';
  document.getElementById('stopsField').hidden = !hasStops;
  document.getElementById('tripLegsField').hidden = !hasStops;
  document.getElementById('tripTransportField').hidden = hasStops;
  document.getElementById('upcomingFields').hidden = form.tripStatus.value !== 'upcoming';
  if (hasStops) renderLegs();
}

function collectTrip(form) {
  const start = form.tripStartDate.value;
  const end = form.tripEndDate.value;
  const status = form.tripStatus.value;
  const stops = form.tripStops.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
  const today = new Date().toISOString().slice(0, 10);
  if (!form.tripOrigin.value.trim() || !form.tripDestination.value.trim() || !start || !end || start > end) throw new Error('Enter valid locations and dates.');
  if (status === 'upcoming' && start < today) throw new Error('Upcoming trips cannot use past dates.');
  if (status === 'completed' && end > today) throw new Error('Completed trips cannot use future dates.');
  if (status === 'upcoming' && (!form.tripBudget.value || !form.tripPeople.value || !form.tripInterests.value.trim())) throw new Error('Add your budget, number of people, and interests for an upcoming trip.');
  if (status === 'upcoming' && (Number(form.tripBudget.value) < 0 || Number(form.tripPeople.value) < 1)) throw new Error('Budget cannot be negative and at least one person must travel.');
  if (form.tripRoute.value === 'stops' && !stops.length) throw new Error('Add at least one stop.');
  const places = [form.tripOrigin.value.trim(), ...(form.tripRoute.value === 'stops' ? stops : []), form.tripDestination.value.trim()];
  const methods = form.tripRoute.value === 'stops' ? [...form.querySelectorAll('[name="leg_transport"]')].map((item) => item.value) : [form.tripTransport.value];
  return { id: form.tripId.value || `${Date.now()}${Math.random()}`, origin: places[0], destination: places[places.length - 1], start_date: start, end_date: end, status, route: form.tripRoute.value, stops, budget: status === 'upcoming' ? Number(form.tripBudget.value) : '', people: status === 'upcoming' ? Number(form.tripPeople.value) : '', interests: status === 'upcoming' ? form.tripInterests.value.trim() : '', legs: places.slice(0, -1).map((from, index) => ({ from, to: places[index + 1], transport: methods[index] || 'Flight' })) };
}

function fillForm(trip) {
  const form = document.getElementById('tripForm');
  form.tripId.value = trip.id; form.tripOrigin.value = trip.origin; form.tripDestination.value = trip.destination;
  form.tripStartDate.value = trip.start_date; form.tripEndDate.value = trip.end_date; form.tripStatus.value = trip.status;
  form.tripRoute.value = trip.route; form.tripTransport.value = trip.legs[0]?.transport || 'Flight'; form.tripStops.value = trip.stops.join('\n');
  form.tripBudget.value = trip.budget; form.tripPeople.value = trip.people; form.tripInterests.value = trip.interests;
  document.getElementById('tripFormTitle').textContent = 'Edit trip';
  document.getElementById('tripFormPanel').hidden = false;
  updateTripFields();
}

function showItinerary(trip) {
  const panel = document.getElementById('tripHistory').closest('.panel');
  panel.querySelector('.generated-itinerary')?.remove();
  const result = document.createElement('section');
  result.className = 'generated-itinerary message success';
  const budget = Number(trip.budget);
  result.innerHTML = `<h4>${tripDays(trip.start_date, trip.end_date)}-day itinerary suggestion</h4><p>Budget plan: ${budget.toLocaleString()} total · ${(budget / Number(trip.people)).toLocaleString()} per person · about ${(budget / tripDays(trip.start_date, trip.end_date)).toLocaleString()} per day</p>`;
  const list = document.createElement('ol');
  itineraryFor(trip).forEach((item) => { const day = document.createElement('li'); day.textContent = `Day ${item.day}: ${item.title} — ${item.activity}`; list.append(day); });
  result.append(list);
  panel.append(result);
}

function renderDashboard() {
  const form = document.getElementById('tripForm');
  if (!form) return;
  const account = currentUser();
  if (!account) return window.location.replace('index.html');
  const trips = account.trips || [];
  document.getElementById('welcomeText').textContent = `Welcome, ${account.name}`;
  document.getElementById('totalTrips').textContent = trips.length;
  document.getElementById('completedTrips').textContent = trips.filter((trip) => trip.status === 'completed').length;
  document.getElementById('upcomingTrips').textContent = trips.filter((trip) => trip.status === 'upcoming').length;
  const list = document.getElementById('tripHistory');
  document.getElementById('emptyTrips').hidden = trips.length > 0;
  list.replaceChildren(...trips.map((trip) => {
    const item = document.createElement('li');
    item.innerHTML = `<strong>${trip.destination}</strong><span>${trip.origin} → ${trip.destination} · ${trip.start_date} to ${trip.end_date} · ${trip.status}</span>`;
    const actions = document.createElement('span');
    actions.innerHTML = '<button class="trip-action" type="button">Edit</button><button class="trip-action delete" type="button">Delete</button>';
    actions.children[0].onclick = () => fillForm(trip);
    actions.children[1].onclick = () => { account.trips = account.trips.filter((item) => item.id !== trip.id); updateAccount(account); renderDashboard(); };
    if (trip.status === 'upcoming') { const button = document.createElement('button'); button.className = 'trip-action'; button.type = 'button'; button.textContent = 'Itinerary'; button.onclick = () => showItinerary(trip); actions.prepend(button); }
    item.append(actions);
    return item;
  }));
}

function bindDashboard() {
  const form = document.getElementById('tripForm');
  if (!form) return;
  renderDashboard();
  document.getElementById('showTripFormBtn').onclick = () => { form.reset(); form.tripId.value = ''; document.getElementById('tripFormTitle').textContent = 'Plan a new trip'; document.getElementById('tripFormPanel').hidden = false; updateTripFields(); };
  document.getElementById('cancelTripBtn').onclick = () => { document.getElementById('tripFormPanel').hidden = true; };
  form.tripRoute.onchange = updateTripFields; form.tripStatus.onchange = updateTripFields;
  [form.tripOrigin, form.tripDestination, form.tripStops].forEach((field) => field.oninput = renderLegs);
  form.onsubmit = (event) => { event.preventDefault(); try { const account = currentUser(); const trip = collectTrip(form); const index = account.trips.findIndex((item) => item.id === trip.id); if (index < 0) account.trips.unshift(trip); else account.trips[index] = trip; updateAccount(account); form.reset(); document.getElementById('tripFormPanel').hidden = true; renderDashboard(); } catch (error) { window.alert(error.message); } };
  document.getElementById('logoutBtn').onclick = () => { localStorage.removeItem(SESSION_KEY); window.location.href = 'index.html'; };
}

document.addEventListener('DOMContentLoaded', () => { bindAuth(); bindDashboard(); });
