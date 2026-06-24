#!/usr/bin/env python3
"""MiniDoom — A minimalistic Doom-like raycaster built with Pygame."""

import sys
import math
import random

sys.stdout.reconfigure(encoding="utf-8")

import pygame

# ── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 960, 600
HALF_W, HALF_H = WIDTH // 2, HEIGHT // 2
FPS = 60
FOV = math.pi / 3
HALF_FOV = FOV / 2
NUM_RAYS = WIDTH // 2
DELTA_ANGLE = FOV / NUM_RAYS
MAX_DEPTH = 20
SCALE = WIDTH // NUM_RAYS
TILE = 1

# ── Colors ───────────────────────────────────────────────────────────────────
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
RED     = (200, 30, 30)
GREEN   = (30, 200, 30)
YELLOW  = (255, 220, 50)
DKGRAY  = (40, 40, 40)
LTGRAY  = (160, 160, 160)

# ── Map ──────────────────────────────────────────────────────────────────────
MAP = [
    "1111111111111111111111111",
    "1000000000000000000000001",
    "1001100000000000001100001",
    "1001100000000000001100001",
    "1000000000110000000000001",
    "1000000000110000000000001",
    "1000000000000000000000001",
    "1000000111111100000000001",
    "1000000100000100000000001",
    "1000000100000100000000001",
    "1000000100000100000000001",
    "1000000000000000000000001",
    "1000000000000000110000001",
    "1000000000000000110000001",
    "1000001100000000000000001",
    "1000001100000000000000001",
    "1000000000000000000000001",
    "1000000000000000000011001",
    "1000000000000000000011001",
    "1000000000000000000000001",
    "1111111111111111111111111",
]

MAP_H = len(MAP)
MAP_W = len(MAP[0])


def is_wall(x, y):
    ix, iy = int(x), int(y)
    if 0 <= ix < MAP_W and 0 <= iy < MAP_H:
        return MAP[iy][ix] != "0"
    return True


def wall_type(x, y):
    ix, iy = int(x), int(y)
    if 0 <= ix < MAP_W and 0 <= iy < MAP_H:
        return int(MAP[iy][ix])
    return 1


# ── Procedural Textures ─────────────────────────────────────────────────────
def make_wall_texture(base_color, brick_color, size=64):
    """Generate a brick-like wall texture."""
    surf = pygame.Surface((size, size))
    surf.fill(base_color)
    bw, bh = size // 4, size // 8
    for row in range(8):
        offset = 0 if row % 2 == 0 else bw // 2
        for col in range(-1, 5):
            rx = col * bw + offset
            ry = row * bh
            rect = pygame.Rect(rx + 1, ry + 1, bw - 2, bh - 2)
            shade = random.randint(-15, 15)
            c = tuple(max(0, min(255, c + shade)) for c in brick_color)
            pygame.draw.rect(surf, c, rect)
    # mortar lines
    for row in range(9):
        y = row * bh
        pygame.draw.line(surf, base_color, (0, y), (size, y))
    for row in range(8):
        offset = 0 if row % 2 == 0 else bw // 2
        for col in range(6):
            x = col * bw + offset
            pygame.draw.line(surf, base_color, (x, row * bh), (x, (row + 1) * bh))
    return surf


TEXTURES = {
    1: make_wall_texture((60, 60, 60), (140, 80, 60)),   # brown brick
}


# ── Player ───────────────────────────────────────────────────────────────────
class Player:
    def __init__(self, x, y, angle):
        self.x, self.y, self.angle = x, y, angle
        self.health = 100
        self.ammo = 50
        self.speed = 3.0
        self.rot_speed = 2.5
        self.shoot_cooldown = 0
        self.damage_flash = 0
        self.kill_count = 0

    def move(self, dx, dy, dt):
        nx = self.x + dx * self.speed * dt
        ny = self.y + dy * self.speed * dt
        margin = 0.2
        if not is_wall(nx + margin * (1 if dx > 0 else -1 if dx < 0 else 0), self.y):
            self.x = nx
        if not is_wall(self.x, ny + margin * (1 if dy > 0 else -1 if dy < 0 else 0)):
            self.y = ny

    def try_shoot(self):
        if self.shoot_cooldown <= 0 and self.ammo > 0:
            self.shoot_cooldown = 0.25
            self.ammo -= 1
            return True
        return False


# ── Enemy ────────────────────────────────────────────────────────────────────
class Enemy:
    SPRITES = None  # built lazily

    @classmethod
    def _make_sprites(cls):
        if cls.SPRITES is not None:
            return
        size = 64
        # Normal sprite
        normal = pygame.Surface((size, size), pygame.SRCALPHA)
        # Body
        pygame.draw.ellipse(normal, (180, 40, 40), (12, 20, 40, 40))
        # Head
        pygame.draw.circle(normal, (200, 60, 60), (32, 16), 12)
        # Eyes
        pygame.draw.circle(normal, (255, 255, 100), (28, 14), 3)
        pygame.draw.circle(normal, (255, 255, 100), (36, 14), 3)
        pygame.draw.circle(normal, BLACK, (28, 14), 1)
        pygame.draw.circle(normal, BLACK, (36, 14), 1)
        # Horns
        pygame.draw.line(normal, (120, 20, 20), (22, 8), (18, 0), 3)
        pygame.draw.line(normal, (120, 20, 20), (42, 8), (46, 0), 3)

        # Hurt sprite (brighter)
        hurt = normal.copy()
        hurt.fill((100, 100, 100, 0), special_flags=pygame.BLEND_RGB_ADD)

        # Dead sprite
        dead = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(dead, (80, 20, 20), (4, 48, 56, 14))

        cls.SPRITES = {"normal": normal, "hurt": hurt, "dead": dead}

    def __init__(self, x, y):
        self._make_sprites()
        self.x, self.y = x, y
        self.health = 30
        self.speed = 1.2
        self.attack_range = 1.5
        self.attack_cd = 0
        self.hurt_timer = 0
        self.alive = True
        self.death_timer = 0

    def update(self, player, dt, enemies):
        if not self.alive:
            self.death_timer -= dt
            return
        self.hurt_timer = max(0, self.hurt_timer - dt)
        self.attack_cd = max(0, self.attack_cd - dt)

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)

        if dist < self.attack_range and self.attack_cd <= 0:
            player.health -= 8
            player.damage_flash = 0.2
            self.attack_cd = 1.0
        elif dist > self.attack_range:
            # Move toward player
            nx = self.x + (dx / dist) * self.speed * dt
            ny = self.y + (dy / dist) * self.speed * dt
            # Avoid other enemies
            blocked = False
            for e in enemies:
                if e is self or not e.alive:
                    continue
                if math.hypot(nx - e.x, ny - e.y) < 0.5:
                    blocked = True
                    break
            if not blocked and not is_wall(nx, ny):
                self.x, self.y = nx, ny

    def take_damage(self, dmg):
        self.health -= dmg
        self.hurt_timer = 0.15
        if self.health <= 0:
            self.alive = False
            self.death_timer = 2.0

    @property
    def sprite(self):
        if not self.alive:
            return self.SPRITES["dead"]
        if self.hurt_timer > 0:
            return self.SPRITES["hurt"]
        return self.SPRITES["normal"]


# ── Raycaster ────────────────────────────────────────────────────────────────
def cast_rays(player):
    """Return list of (depth, wall_type, texture_x) for each ray column."""
    walls = []
    for ray in range(NUM_RAYS):
        angle = player.angle - HALF_FOV + ray * DELTA_ANGLE
        sin_a, cos_a = math.sin(angle), math.cos(angle)

        depth = MAX_DEPTH
        hit_type = 1
        tex_x = 0.0

        # DDA-style raycasting
        for depth_i in range(1, MAX_DEPTH * 100):
            t = depth_i / 100.0
            x = player.x + t * cos_a
            y = player.y + t * sin_a
            if is_wall(x, y):
                depth = t
                hit_type = wall_type(x, y)
                # Texture X coordinate
                if abs(cos_a) > abs(sin_a):
                    tex_x = y % 1
                else:
                    tex_x = x % 1
                break

        # Fix fisheye
        depth *= math.cos(player.angle - angle)
        walls.append((depth, hit_type, tex_x))
    return walls


# ── Rendering ────────────────────────────────────────────────────────────────
def render_3d(surface, player, walls, enemies):
    """Render the 3D view with walls, floor/ceiling, and sprites."""
    # Ceiling gradient
    for y in range(0, HALF_H, 4):
        t = y / HALF_H
        c = int(20 + 30 * t)
        pygame.draw.rect(surface, (c, c, c + 10), (0, y, WIDTH, 4))

    # Floor gradient
    for y in range(HALF_H, HEIGHT, 4):
        t = (y - HALF_H) / HALF_H
        c = int(20 + 40 * t)
        pygame.draw.rect(surface, (c, c - 5, c - 10), (0, y, WIDTH, 4))

    # Walls
    z_buffer = []
    for ray, (depth, wtype, tex_x) in enumerate(walls):
        if depth <= 0:
            depth = 0.001
        wall_height = min(HEIGHT, int(HEIGHT / depth))
        brightness = max(0.08, 1.0 - depth / MAX_DEPTH)
        x = ray * SCALE

        # Draw textured wall strip
        tex = TEXTURES.get(wtype, TEXTURES[1])
        tex_col = int(tex_x * tex.get_width()) % tex.get_width()
        strip = tex.subsurface(pygame.Rect(tex_col, 0, 1, tex.get_height()))
        strip = pygame.transform.scale(strip, (SCALE, wall_height))
        # Apply distance shading
        shade_surf = pygame.Surface((SCALE, wall_height))
        shade_surf.fill((0, 0, 0))
        shade_surf.set_alpha(int(255 * (1 - brightness)))
        strip.blit(shade_surf, (0, 0))

        y_offset = HALF_H - wall_height // 2
        surface.blit(strip, (x, y_offset))
        z_buffer.append(depth)

    # Sprites (enemies)
    sprite_list = []
    for enemy in enemies:
        dx = enemy.x - player.x
        dy = enemy.y - player.y
        dist = math.hypot(dx, dy)
        if dist < 0.3:
            continue
        angle_to = math.atan2(dy, dx)
        delta = angle_to - player.angle
        # Normalize
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        if abs(delta) < HALF_FOV + 0.3:
            sprite_list.append((dist, delta, enemy))

    # Sort far to near
    sprite_list.sort(key=lambda s: -s[0])

    for dist, delta, enemy in sprite_list:
        screen_x = int(HALF_W + delta / HALF_FOV * HALF_W)
        sprite_h = min(HEIGHT * 2, int(HEIGHT / dist))
        sprite_w = sprite_h  # square sprite
        brightness = max(0.1, 1.0 - dist / MAX_DEPTH)

        spr = enemy.sprite
        scaled = pygame.transform.scale(spr, (sprite_w, sprite_h))
        # Apply shading
        shade_surf = pygame.Surface((sprite_w, sprite_h), pygame.SRCALPHA)
        shade_surf.fill((0, 0, 0, int(255 * (1 - brightness))))
        scaled.blit(shade_surf, (0, 0))

        sx = screen_x - sprite_w // 2
        sy = HALF_H - sprite_h // 2 + int(sprite_h * 0.15)  # feet on floor

        # Z-buffer clipping: only draw if in front of walls
        ray_idx = int((screen_x) / SCALE)
        if 0 <= ray_idx < len(z_buffer) and dist < z_buffer[ray_idx] + 0.3:
            surface.blit(scaled, (sx, sy))

    return z_buffer


def render_minimap(surface, player, enemies):
    """Draw a small minimap in the top-left corner."""
    cell = 6
    ox, oy = 10, 10
    # Background
    bg = pygame.Surface((MAP_W * cell + 2, MAP_H * cell + 2), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    surface.blit(bg, (ox - 1, oy - 1))

    for y in range(MAP_H):
        for x in range(MAP_W):
            if MAP[y][x] != "0":
                pygame.draw.rect(surface, (100, 100, 100),
                                 (ox + x * cell, oy + y * cell, cell, cell))
    # Enemies
    for e in enemies:
        if e.alive:
            pygame.draw.circle(surface, RED,
                               (int(ox + e.x * cell), int(oy + e.y * cell)), 2)
    # Player
    px = int(ox + player.x * cell)
    py = int(oy + player.y * cell)
    pygame.draw.circle(surface, GREEN, (px, py), 3)
    # Direction line
    dx = int(math.cos(player.angle) * 10)
    dy = int(math.sin(player.angle) * 10)
    pygame.draw.line(surface, GREEN, (px, py), (px + dx, py + dy), 1)


def render_hud(surface, player, game_time):
    """Draw the heads-up display."""
    font = pygame.font.SysFont("consolas", 20, bold=True)
    big_font = pygame.font.SysFont("consolas", 36, bold=True)

    # Health bar
    bar_w, bar_h = 200, 20
    bx, by = 20, HEIGHT - 50
    pygame.draw.rect(surface, (40, 40, 40), (bx, by, bar_w, bar_h))
    hp_ratio = max(0, player.health / 100)
    hp_color = GREEN if hp_ratio > 0.5 else YELLOW if hp_ratio > 0.25 else RED
    pygame.draw.rect(surface, hp_color, (bx, by, int(bar_w * hp_ratio), bar_h))
    pygame.draw.rect(surface, WHITE, (bx, by, bar_w, bar_h), 2)
    hp_text = font.render(f"HP {player.health}", True, WHITE)
    surface.blit(hp_text, (bx + 5, by + 1))

    # Ammo
    ammo_text = font.render(f"⚡ AMMO {player.ammo}", True, YELLOW)
    surface.blit(ammo_text, (bx + bar_w + 20, by + 1))

    # Kills
    kill_text = font.render(f"☠ KILLS {player.kill_count}", True, RED)
    surface.blit(kill_text, (bx + bar_w + 160, by + 1))

    # Crosshair
    cx, cy = HALF_W, HALF_H
    size = 12
    pygame.draw.line(surface, (255, 255, 255, 180), (cx - size, cy), (cx + size, cy), 2)
    pygame.draw.line(surface, (255, 255, 255, 180), (cx, cy - size), (cx, cy + size), 2)

    # Damage flash
    if player.damage_flash > 0:
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        alpha = int(min(255, player.damage_flash * 800))
        flash.fill((255, 0, 0, alpha))
        surface.blit(flash, (0, 0))

    # Shoot flash
    if player.shoot_cooldown > 0.2:
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 255, 200, 40))
        surface.blit(flash, (0, 0))

    # Death screen
    if player.health <= 0:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        dead_text = big_font.render("YOU DIED", True, RED)
        surface.blit(dead_text, (HALF_W - dead_text.get_width() // 2, HALF_H - 40))
        restart_text = font.render("Press R to restart", True, WHITE)
        surface.blit(restart_text, (HALF_W - restart_text.get_width() // 2, HALF_H + 20))


def render_weapon(surface, player, game_time):
    """Draw the weapon at the bottom of the screen."""
    # Gun bob
    bob = math.sin(game_time * 6) * 3 if abs(math.sin(player.angle)) > 0.01 else 0
    # Recoil
    recoil = max(0, player.shoot_cooldown - 0.15) * 80

    cx = HALF_W
    cy = HEIGHT - 80 + int(bob) + int(recoil)

    # Gun body
    pygame.draw.rect(surface, (60, 60, 60), (cx - 8, cy - 40, 16, 50))
    pygame.draw.rect(surface, (80, 80, 80), (cx - 6, cy - 38, 12, 46))
    # Barrel
    pygame.draw.rect(surface, (50, 50, 50), (cx - 4, cy - 70, 8, 35))
    pygame.draw.rect(surface, (70, 70, 70), (cx - 3, cy - 68, 6, 30))
    # Muzzle flash
    if player.shoot_cooldown > 0.18:
        flash_r = random.randint(12, 20)
        pygame.draw.circle(surface, YELLOW, (cx, cy - 72), flash_r)
        pygame.draw.circle(surface, WHITE, (cx, cy - 72), flash_r // 2)


# ── Game ─────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("MiniDoom")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)
        self.reset()

    def reset(self):
        self.player = Player(2.5, 2.5, 0)
        self.enemies = [
            Enemy(8.5, 3.5), Enemy(14.5, 5.5), Enemy(6.5, 10.5),
            Enemy(12.5, 12.5), Enemy(18.5, 8.5), Enemy(20.5, 16.5),
            Enemy(4.5, 16.5), Enemy(10.5, 18.5), Enemy(16.5, 15.5),
            Enemy(22.5, 3.5), Enemy(3.5, 8.5), Enemy(14.5, 18.5),
        ]
        self.game_time = 0
        self.running = True

    def handle_input(self, dt):
        keys = pygame.key.get_pressed()
        p = self.player
        cos_a, sin_a = math.cos(p.angle), math.sin(p.angle)

        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += cos_a; dy += sin_a
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= cos_a; dy -= sin_a
        if keys[pygame.K_a]:
            dx += sin_a; dy -= cos_a
        if keys[pygame.K_d]:
            dx -= sin_a; dy += cos_a

        # Normalize diagonal movement
        length = math.hypot(dx, dy)
        if length > 0:
            dx, dy = dx / length, dy / length

        p.move(dx, dy, dt)

        if keys[pygame.K_LEFT]:
            p.angle -= p.rot_speed * dt
        if keys[pygame.K_RIGHT]:
            p.angle += p.rot_speed * dt

        # Mouse look
        mx, _ = pygame.mouse.get_rel()
        if pygame.mouse.get_focused():
            p.angle += mx * 0.003

        # Shooting
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:
            if p.try_shoot():
                self.hit_scan()

    def hit_scan(self):
        """Cast a ray from the player and check if it hits an enemy."""
        p = self.player
        cos_a, sin_a = math.cos(p.angle), math.sin(p.angle)

        best_enemy = None
        best_dist = MAX_DEPTH

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dx = enemy.x - p.x
            dy = enemy.y - p.y
            dist = math.hypot(dx, dy)
            if dist >= best_dist:
                continue
            # Check if enemy is near the ray
            angle_to = math.atan2(dy, dx)
            delta = angle_to - p.angle
            while delta > math.pi: delta -= 2 * math.pi
            while delta < -math.pi: delta += 2 * math.pi
            # Hit radius decreases with distance
            hit_radius = 0.3 / max(dist, 0.5)
            if abs(delta) < hit_radius:
                # Check no wall between
                blocked = False
                for t_step in range(1, int(dist * 20)):
                    t = t_step / 20.0
                    if is_wall(p.x + t * cos_a, p.y + t * sin_a):
                        blocked = True
                        break
                if not blocked:
                    best_enemy = enemy
                    best_dist = dist

        if best_enemy:
            dmg = max(10, int(30 - best_dist * 2))
            best_enemy.take_damage(dmg)
            if not best_enemy.alive:
                p.kill_count += 1

    def update(self, dt):
        self.game_time += dt
        self.player.shoot_cooldown = max(0, self.player.shoot_cooldown - dt)
        self.player.damage_flash = max(0, self.player.damage_flash - dt)

        for e in self.enemies:
            e.update(self.player, dt, self.enemies)

        # Remove long-dead enemies
        self.enemies = [e for e in self.enemies if e.alive or e.death_timer > 0]

    def draw(self):
        walls = cast_rays(self.player)
        self.screen.fill(BLACK)
        render_3d(self.screen, self.player, walls, self.enemies)
        render_weapon(self.screen, self.player, self.game_time)
        render_minimap(self.screen, self.player, self.enemies)
        render_hud(self.screen, self.player, self.game_time)

        # FPS counter
        fps_text = self.font.render(f"FPS: {int(self.clock.get_fps())}", True, LTGRAY)
        self.screen.blit(fps_text, (WIDTH - 100, 10))

        pygame.display.flip()

    def run(self):
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)

        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # Cap delta time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_r and self.player.health <= 0:
                        self.reset()

            if self.player.health > 0:
                self.handle_input(dt)
            self.update(dt)
            self.draw()

        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        pygame.quit()


# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Game().run()
