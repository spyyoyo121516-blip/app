// Kingdom Big Game - Client JS
// Load on game.html

class KingdomGame {
    constructor() {
        this.username = '';
        this.hero = {};
        this.stats = {};
        this.currentBattle = null;
        this.pollInterval = null;
        this.init();
    }

    async init() {
        const res = await fetch('/api/kingdom/session');
        if (!res.ok) {
            window.location.href = '/kingdom';
            return;
        }
        const session = await res.json();
        this.username = session.username;

        await this.loadData();
        this.render();
        this.bindEvents();
        this.startPolling();
    }

    async loadData() {
        const res = await fetch('/api/kingdom/stats');
        const data = await res.json();
        this.hero = data.hero;
        this.stats = data.stats;
    }

    async createBattle(type = 'solo', botCount = 1, maxPlayers = 4) {
        const res = await fetch('/api/kingdom/battles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({type, bot_count: botCount, max_players: maxPlayers})
        });
        const data = await res.json();
        if (data.status === 'success') {
            this.currentBattle = data.battle;
            this.renderBattle();
        }
    }

    async joinBattle(battleId) {
        const res = await fetch(`/api/kingdom/battle/${battleId}/join`, {method: 'POST'});
        const data = await res.json();
        if (data.status === 'success') {
            this.currentBattle = data.battle;
            this.renderBattle();
        }
    }

    async loadBattle(battleId) {
        const res = await fetch(`/api/kingdom/battle/${battleId}`);
        const data = await res.json();
        if (data.status === 'success') {
            this.currentBattle = data.battle;
            this.renderBattle();
        }
    }

    async usePower(battleId, powerIdx) {
        const res = await fetch(`/api/kingdom/battle/${battleId}/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({power_idx: powerIdx})
        });
        const data = await res.json();
        if (data.status === 'success') {
            this.currentBattle = data.battle;
            await this.loadData();  // Update stats
            this.renderBattle();
        }
    }

    startPolling() {
        this.pollInterval = setInterval(async () => {
            if (this.currentBattle) {
                await this.loadBattle(this.currentBattle.id);
            }
        }, 3000);
    }

    render() {
        document.getElementById('coins').textContent = this.stats.coins;
        document.getElementById('score').textContent = this.stats.score;
        document.getElementById('wins').textContent = this.stats.wins;
        document.getElementById('level').textContent = this.stats.level;
        
        const heroImg = document.getElementById('hero-img');
        if (this.hero.sprite) {
            heroImg.src = this.hero.sprite;
            heroImg.style.display = 'block';
        }
        
        const powersList = document.getElementById('hero-powers');
        powersList.innerHTML = '';
        (this.hero.powers || []).forEach((power, i) => {
            const li = document.createElement('li');
            li.textContent = power;
            powersList.appendChild(li);
        });
    }

    renderBattle() {
        if (!this.currentBattle) return;
        
        document.getElementById('battle-id').textContent = this.currentBattle.id;
        document.getElementById('battle-type').textContent = this.currentBattle.type;
        document.getElementById('battle-state').textContent = this.currentBattle.state;
        
        // Health bars
        const arena = document.getElementById('battle-arena');
        arena.innerHTML = '';
        const combatants = [...this.currentBattle.players, ...this.currentBattle.bots];
        combatants.forEach(name => {
            const hp = this.currentBattle.healths[name] || 0;
            const div = document.createElement('div');
            div.className = `combatant ${name === this.username ? 'me' : ''}`;
            div.innerHTML = `
                <div>${name}</div>
                <div class="health-bar">
                    <div class="health-fill" style="width: ${Math.max(0, (hp/100)*100)}%"></div>
                </div>
                <div>${hp}/100</div>
            `;
            arena.appendChild(div);
        });
        
        // Powers - check cooldowns
        const turn = this.currentBattle.turn;
        const myCooldowns = this.currentBattle.cooldowns[this.username] || [];
        const powers = document.querySelectorAll('.power-btn');
        powers.forEach((btn, i) => {
            if (myCooldowns[i] > turn) {
                btn.disabled = true;
                btn.textContent = `${(myCooldowns[i] - turn)}s`;
            } else {
                btn.disabled = false;
                btn.textContent = `Power ${i+1}`;
            }
        });
        
        if (this.currentBattle.state === 'finished') {
            document.getElementById('battle-complete').style.display = 'block';
        }
    }

    bindEvents() {
        // Battle create
        document.getElementById('create-solo').onclick = () => this.createBattle('solo', 3);
        document.getElementById('create-ffa').onclick = () => this.createBattle('ffa', 0, 4);
        document.getElementById('create-bot-battle').onclick = () => this.createBattle('bot_battle', 5);
        
        // Power buttons
        document.querySelectorAll('.power-btn').forEach((btn, i) => {
            btn.onclick = () => {
                if (this.currentBattle) {
                    this.usePower(this.currentBattle.id, i);
                }
            };
        });
    }
}

// Init
const game = new KingdomGame();

