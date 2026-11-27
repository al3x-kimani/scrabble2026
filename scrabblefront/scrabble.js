const API_URL = "http://localhost:5000/api";

let players = [];
let results = [];
let gameResults = [];
let toastTimer;

// Communicate with Flask
async function apiRequest(endpoint, options = {}) {
    const response = await fetch(API_URL + endpoint, {
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}

// Display notifications
function showToast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// Load players from SQLite through Flask
async function loadPlayers() {
    const data = await apiRequest("/players");

    players = data.players.map(player => ({
        id: player.player_id,
        name: player.full_name,
        email: player.email,
        level: player.level
    }));
}

// Load leaderboard from Flask
async function loadLeaderboard() {
    const data = await apiRequest("/leaderboard");

    results = data.leaderboard;
}
// Load individual competition results
async function loadGameResults() {
    const data = await apiRequest("/results");

    gameResults = data.results;
}
// Calculate player statistics
function getPlayerStats(playerId) {
    const player = results.find(
        item => item.player_id === playerId
    );

    if (!player) {
        return { games: 0, total: 0, average: 0 };
    }

    return {
        games: player.total_rounds,
        total: player.total_marks,
        average: player.total_rounds
            ? player.total_marks / player.total_rounds
            : 0
    };
}

// Navigation
function showView(viewId) {
    document.querySelectorAll(".view").forEach(view => {
        view.classList.toggle("active", view.id === viewId);
    });

    document.querySelectorAll(".nav-button").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.view === viewId
        );
    });

    renderAll();
}

document.querySelectorAll(".nav-button").forEach(button => {
    button.addEventListener("click", () => {
        showView(button.dataset.view);
    });
});

document.querySelectorAll("[data-go]").forEach(button => {
    button.addEventListener("click", () => {
        showView(button.dataset.go);
    });
});

// Register player
document.getElementById("player-form").addEventListener(
    "submit",
    async event => {
        event.preventDefault();

        const name = document.getElementById("player-name")
            .value.trim();

        const email = document.getElementById("player-email")
            .value.trim();

        const level = document.getElementById("player-level").value;

        if (!name || !email) {
            showToast("Name and email are required.");
            return;
        }

        try {
            const data = await apiRequest("/players", {
                method: "POST",
                body: JSON.stringify({
                    full_name: name,
                    email: email,
                    level: level
                })
            });

            await refreshData();

            event.target.reset();

            showToast(
                data.player.full_name +
                " registered! ID: " +
                data.player.player_id
            );

            showView("players");

        } catch (error) {
            showToast(error.message);
        }
    }
);

// Populate player selection
function renderPlayerOptions() {
    const select = document.getElementById("result-player");
    const previousValue = select.value;

    select.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = players.length
        ? "Choose a player"
        : "Register a player first";

    select.appendChild(placeholder);

    players.forEach(player => {
        const option = document.createElement("option");

        option.value = player.id;
        option.textContent =
            player.name + " (" + player.id + ")";

        select.appendChild(option);
    });

    if (players.some(player => player.id === previousValue)) {
        select.value = previousValue;
    }
}

// Record competition marks
document.getElementById("result-form").addEventListener(
    "submit",
    async event => {
        event.preventDefault();
        const admin = await checkAdminSession();
        if (!admin) {
        showToast("Please log in as an administrator first.");
         showView("admin-login");
          return;
          }
        const playerId =
            document.getElementById("result-player").value;

        const roundNumber = Number(
            document.getElementById("round-number").value
        );

        const marks = Number(
            document.getElementById("game-marks").value
        );

        if (!players.some(player => player.id === playerId)) {
            showToast("Please select a registered player.");
            return;
        }

        if (!Number.isSafeInteger(roundNumber) ||
            roundNumber <= 0) {
            showToast("Enter a valid round number.");
            return;
        }

        if (!Number.isSafeInteger(marks) || marks < 0) {
            showToast("Enter valid non-negative marks.");
            return;
        }

        try {
            await apiRequest("/results", {
                method: "POST",
                body: JSON.stringify({
                    player_id: playerId,
                    round_number: roundNumber,
                    marks: marks
                })
            });

            await refreshData();

            event.target.reset();

            showToast("Competition marks recorded successfully.");

            showView("leaderboard");

        } catch (error) {
            showToast(error.message);
        }
    }
);

// Display leaderboard
function renderLeaderboard() {
    const tbody = document.getElementById("ranking-list");

    const query = document.getElementById("leaderboard-search")
        .value.trim().toLowerCase();

    tbody.replaceChildren();

    const filtered = results.filter(player =>
        player.full_name.toLowerCase().includes(query) ||
        player.player_id.toLowerCase().includes(query)
    );

    filtered.forEach(player => {
        const stats = getPlayerStats(player.player_id);

        const row = document.createElement("tr");

        const values = [
            "#" + player.position,
            player.full_name,
            stats.games,
            stats.total.toLocaleString(),
            stats.average.toFixed(1)
        ];

        values.forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = value;

            if (index === 1) {
                cell.className = "player-name-cell";
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });

    document.getElementById("leaderboard-empty").hidden =
        filtered.length > 0;

    document.getElementById("total-players").textContent =
        players.length;

    document.getElementById("total-games").textContent =
        results.reduce(
            (sum, player) => sum + player.total_rounds,
            0
        );

    document.getElementById("highest-score").textContent =
        results.length
            ? Math.max(...results.map(p => p.total_marks))
                .toLocaleString()
            : "0";
}

// Display all registered players
function renderPlayers() {
    const tbody = document.getElementById("player-list");

    const query = document.getElementById("player-search")
        .value.trim().toLowerCase();

    tbody.replaceChildren();

    const filtered = players.filter(player =>
        player.name.toLowerCase().includes(query) ||
        player.id.toLowerCase().includes(query) ||
        player.email.toLowerCase().includes(query)
    );

    filtered.forEach(player => {
        const stats = getPlayerStats(player.id);

        const row = document.createElement("tr");

        const values = [
            player.id,
            player.name,
            player.email,
            player.level,
            stats.total.toLocaleString(),
            stats.games
        ];

        values.forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = value;

            if (index === 1) {
                cell.className = "player-name-cell";
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });

    document.getElementById("players-empty").hidden =
        filtered.length > 0;
}
// Display individual results for administrators
function renderManagedResults() {
    const tbody = document.getElementById("results-management-list");
    const emptyMessage = document.getElementById("results-management-empty");

    if (!tbody || !emptyMessage) return;

    tbody.replaceChildren();

    gameResults.forEach(result => {
        const row = document.createElement("tr");

        const playerCell = document.createElement("td");
        playerCell.textContent = result.full_name;

        const roundCell = document.createElement("td");
        roundCell.textContent = result.round_number;

        const marksCell = document.createElement("td");
        marksCell.textContent = result.marks;

        const actionsCell = document.createElement("td");

        const editButton = document.createElement("button");
        editButton.textContent = "Edit";
        editButton.className = "secondary";
        editButton.addEventListener("click", () => editResult(result));

        const deleteButton = document.createElement("button");
        deleteButton.textContent = "Delete";
        deleteButton.className = "danger";
        deleteButton.addEventListener("click", () => deleteResult(result));

        actionsCell.append(editButton, deleteButton);

        row.append(
            playerCell,
            roundCell,
            marksCell,
            actionsCell
        );

        tbody.appendChild(row);
    });

    emptyMessage.hidden = gameResults.length > 0;
}
// Edit an existing competition result
async function editResult(result) {
    const newRound = prompt(
        "Enter the new round number:",
        result.round_number
    );

    if (newRound === null) return;

    const newMarks = prompt(
        "Enter the new marks:",
        result.marks
    );

    if (newMarks === null) return;

    const roundNumber = Number(newRound);
    const marks = Number(newMarks);

    if (!Number.isSafeInteger(roundNumber) || roundNumber <= 0) {
        showToast("Enter a valid positive round number.");
        return;
    }

    if (!Number.isFinite(marks) || marks < 0) {
        showToast("Enter valid non-negative marks.");
        return;
    }

    try {
        await apiRequest("/results/" + result.id, {
            method: "PUT",
            body: JSON.stringify({
                round_number: roundNumber,
                marks: marks
            })
        });

        await refreshData();
        showToast("Competition result updated successfully.");

    } catch (error) {
        showToast(error.message);
    }
}
// Delete an existing competition result
async function deleteResult(result) {
    const confirmed = confirm(
        "Are you sure you want to delete the result for " +
        result.full_name +
        " in round " +
        result.round_number +
        "?"
    );

    if (!confirmed) return;

    try {
        await apiRequest("/results/" + result.id, {
            method: "DELETE"
        });

        await refreshData();

        showToast("Competition result deleted successfully.");

    } catch (error) {
        showToast(error.message);
    }
}
// Render all website sections
function renderAll() {
    renderPlayerOptions();
    renderLeaderboard();
    renderPlayers();
    renderManagedResults();
}
// Refresh information from the database
async function refreshData() {
    await loadPlayers();
    await loadLeaderboard();

    try {
        await loadGameResults();
    } catch (error) {
        gameResults = [];
    }

    renderAll();
}

// Search functionality
document.getElementById("leaderboard-search").addEventListener(
    "input",
    renderLeaderboard
);

document.getElementById("player-search").addEventListener(
    "input",
    renderPlayers
);
// Administrator login
// Administrator login
async function adminLogin(email, password) {
    try {
        const data = await apiRequest("/admin/login", {
            method: "POST",
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        showToast("Welcome, " + data.admin.full_name);

        return data.admin;

    } catch (error) {
        showToast(error.message);
        return null;
    }
}
// Administrator logout
async function adminLogout() {
    try {
        await apiRequest("/admin/logout", {
            method: "POST"
        });

        showToast("You have logged out successfully.");
        showView("admin-login");

    } catch (error) {
        showToast(error.message);
    }
}
// Check administrator session
async function checkAdminSession() {
    try {
        const data = await apiRequest("/admin/me");

        if (data.logged_in) {
            return data.admin;
        }

        return null;

    } catch (error) {
        return null;
    }
}
// Handle administrator logout button
document.getElementById("admin-logout").addEventListener(
    "click",
    adminLogout
);
// Handle administrator login form
document.getElementById("admin-login-form").addEventListener(
    "submit",
    async event => {
        event.preventDefault();

        const email = document.getElementById("admin-email").value.trim();
        const password = document.getElementById("admin-password").value;

        const admin = await adminLogin(email, password);

        if (admin) {
            event.target.reset();

            await loadGameResults();
            renderManagedResults();

            showToast("Logged in as " + admin.role);
            showView("results");
        }
    }
);