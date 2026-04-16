// Kingdom Royale - Clash Royale Clone Overlay
class KingdomRoyale {
    constructor(game) {
        this.game = game;
        this.elixir = 10;
        this.elixirMax = 10;
        this.elixirRegenRate = 0.5; // per 0.5s
        this.regenInterval = null;
        this.lanes = [{units: [], enemyUnits: []}, {units: [], enemyUnits: []}, {units: [], enemyUnits: []}];
        this.kingHp = 300;
        this.enemyKingHp = 300;
        this.cards = [
            {name: 'Knight', elixir: 3, dmg: 100, hp: 150},
            {name: 'Archer', elixir: 2, dmg: 80, hp: 80, range: true},
            {name: 'Wizard', elixir: 4, dmg: 200, hp: 100, aoe: true},
            {name: 'Golem', elixir: 8, dmg: 300, hp: 400}
        ];
        this.init();
    }

    init() {
        this.renderArena();
        this.renderCards();
        this.startElixirRegen();
        setInterval(() => this.gameTick(), 500);
    }

    renderArena() {
        const arena = document.getElementById('battle-arena');
        arena.innerHTML = `
            <div class="royale-bg"></div>
            <div class="lane">
                <div class="tower-hp">King: ${this.kingHp}</div>
                <div class="king-tower"></div>
            </div>
            <div class="lane"><!-- lane 1 --></div>
            <div class="lane"><!-- lane 2 --></div>
            <div class="lane"><!-- lane 3 --></div>
            <div class="enemy-tower" style="position:absolute; top:10%; right:50%; transform:translateX(50%);">
                <div class="tower-hp enemy" style="left:auto;">Enemy: ${this.enemyKingHp}</div>
                <div class="king-tower enemy"></div>
            </div>
        `;
        arena.className = 'royale-arena';
    }

    renderCards() {
        const container = document.querySelector('.card-slot');
        container.innerHTML = '';
        this.cards.forEach((card, i) => {
            const btn = document.createElement('div');
            btn.className = 'card';
            btn.innerHTML = `<div>${card.name}</div><div>${card.elixir}</div>`;
            btn.onclick = () => this.playCard(i, 1); // lane 1 default
            container.appendChild(btn);
        });
        this.updateElixirBar();
    }

    updateElixirBar() {
        document.querySelector('.elixir-fill').style.width = `${(this.elixir/this.elixirMax)*100}%`;
        document.querySelector('.elixir-count').textContent = Math.floor(this.elixir);
    }

    startElixirRegen() {
        this.regenInterval = setInterval(() => {
            this.elixir = Math.min(this.elixirMax, this.elixir + this.elixirRegenRate);
            this.updateElixirBar();
        }, 500);
    }

    playCard(cardIdx, laneIdx) {
        const card = this.cards[cardIdx];
        if (this.elixir < card.elixir) return alert('Not enough elixir!');
        
        this.elixir -= card.elixir;
        this.updateElixirBar();
        
        // Spawn unit
        this.lanes[laneIdx-1].units.push({...card});
        this.renderLane(laneIdx-1);
        
        // Animate to enemy
        setTimeout(() => this.attackUnits(laneIdx-1), 2000);
    }

    renderLane(laneIdx) {
        const laneEl = document.querySelectorAll('.lane')[laneIdx];
        const unitsHtml = this.lanes[laneIdx].units.map(u => 
            `<div class="unit" style="animation-duration:2s;"></div>`
        ).join('');
        laneEl.innerHTML += unitsHtml;
    }

    attackUnits(laneIdx) {
        // Simple dmg to enemy king
        const totalDmg = this.lanes[laneIdx].units.reduce((sum, u) => sum + u.dmg, 0);
        this.enemyKingHp -= totalDmg * 0.5; // 50% reach
        this.enemyKingHp = Math.max(0, this.enemyKingHp);
        document.querySelectorAll('.tower-hp')[1].textContent = `Enemy: ${this.enemyKingHp}`;
        
        // Enemy counter (bots)
        this.kingHp -= 50;
        document.querySelector('.tower-hp').textContent = `King: ${this.kingHp}`;
        
        this.lanes[laneIdx].units = []; // Clear after attack
        this.checkWin();
    }

    gameTick() {
        // Enemy AI: spawn random
        if (Math.random() < 0.3) {
            const randLane = Math.floor(Math.random()*3);
            this.lanes[randLane].enemyUnits.push(this.cards[Math.floor(Math.random()*4)]);
        }
    }

    checkWin() {
        if (this.enemyKingHp <= 0) {
            alert('Victory! +100 coins');
            this.game.usePower('win', 100); // Reward
        } else if (this.kingHp <= 0) {
            alert('Defeat!');
        }
    }
}

// Extend KingdomGame
const royaleOverlay = new KingdomRoyale(game);
