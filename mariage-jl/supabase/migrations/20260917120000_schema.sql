-- =====================================================================
-- V0 — Schéma de l'application du mariage J&L
-- Source : docs/PLAN.md §4. Région Supabase : Europe (question V0-06).
-- Aucune donnée inventée : tout ce qui est inconnu est NULL et reste
-- éditable depuis l'espace admin.
-- =====================================================================

create schema if not exists jl;

-- ---------------------------------------------------------------- Paramètres
-- Regroupe la date du mariage et la bascule manuelle des périodes
-- (docs/PLAN.md prévoyait une table periods_override : fusionnée ici,
-- une seule ligne, pour que la date de référence des purges soit unique).
create table public.parametres (
  id smallint primary key default 1 check (id = 1),
  date_mariage date not null,
  date_limite_reponse date,                       -- [À COMPLÉTER] question V1-02
  periode_forcee text check (periode_forcee in ('avant','semaine','jour','apres')),
  periode_forcee_jusqu_a timestamptz,
  maj_le timestamptz not null default now()
);

insert into public.parametres (id, date_mariage) values (1, date '2028-06-03');

-- ---------------------------------------------------------------- Accès
create table public.households (
  id uuid primary key default gen_random_uuid(),
  label_public text not null,                     -- « Famille … » affiché à l'ouverture
  token_sha256 bytea not null unique,             -- jamais le jeton en clair
  backup_code_sha256 bytea not null unique,       -- code de secours à 6 caractères
  lang_default text not null default 'fr' check (lang_default in ('fr','en')),
  comfort_prefs jsonb not null default '{}'::jsonb,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.household_links (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  purpose text not null default 'share' check (purpose = 'share'),
  token_sha256 bytea not null unique,
  max_opens smallint not null default 5 check (max_opens > 0),
  opens smallint not null default 0 check (opens >= 0),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
create index on public.household_links (household_id);

create table public.guests (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  first_name text not null,
  last_name text,
  is_child boolean not null default false,
  age_years smallint check (age_years between 0 and 120),
  menu_choice text,                               -- options [À COMPLÉTER] question V1-08
  diet_flags text[] not null default '{}',
  sort_order smallint not null default 0
);
create index on public.guests (household_id);

-- ---------------------------------------------------------------- Moments
create table public.moments (
  id text primary key check (id in ('01','02','03','04','05')),
  name_fr text not null,
  name_en text not null,
  kind_fr text not null,
  kind_en text not null,
  color_token text not null,
  starts_at timestamptz,                          -- [À COMPLÉTER] question V1-06
  ends_at timestamptz,
  place text,
  ambience_fr text,
  ambience_en text,
  detail_fr text,
  detail_en text,
  shift_minutes integer not null default 0        -- décalage posé par la régie
);

insert into public.moments (id, name_fr, name_en, kind_fr, kind_en, color_token) values
  ('01', 'L’Éclat',      'L’Éclat',      'Accueil',   'Welcome',     'eclat'),
  ('02', 'L’Horizon',    'L’Horizon',    'Cérémonie', 'Ceremony',    'horizon'),
  ('03', 'La Rencontre',  'La Rencontre',  'Cocktail',  'Cocktail',    'rencontre'),
  ('04', 'L’Ivresse',    'L’Ivresse',    'Dîner',     'Dinner',      'ivresse'),
  ('05', 'La Nuit',       'La Nuit',       'Fête',      'Celebration', 'nuit');

-- ---------------------------------------------------------------- Réponse
create table public.rsvp (
  household_id uuid primary key references public.households(id) on delete cascade,
  status text not null check (status in ('yes','no','maybe')),
  submitted_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  locked_at timestamptz,
  song_request text,
  message_to_couple text,
  lodging_note text,
  transport_note text
);

create table public.rsvp_attendance (
  guest_id uuid not null references public.guests(id) on delete cascade,
  moment_id text not null references public.moments(id),
  attending boolean not null default true,
  primary key (guest_id, moment_id)
);

-- Donnée de santé : consentement explicite séparé et purge automatique (§11).
create table public.health_allergies (
  guest_id uuid primary key references public.guests(id) on delete cascade,
  content text not null,
  consent_at timestamptz not null,
  consent_text_version text not null,
  purge_after date not null
);

create table public.reminder_optin (
  household_id uuid primary key references public.households(id) on delete cascade,
  email text not null,
  consent_at timestamptz not null,
  unsubscribe_token_sha256 bytea not null unique,
  revoked_at timestamptz
);

create table public.push_subscription (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- Contenus
create table public.content_blocks (
  key text not null,
  locale text not null check (locale in ('fr','en')),
  value jsonb not null,
  updated_at timestamptz not null default now(),
  updated_by text,
  primary key (key, locale)
);

create table public.faq (
  id uuid primary key default gen_random_uuid(),
  sort_order smallint not null default 0,
  question_fr text not null,
  question_en text not null,
  answer_fr text not null,
  answer_en text not null,
  published boolean not null default false
);

create table public.accommodations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  distance_km numeric(5,1),
  price_hint text,
  url text,
  phone text,
  shuttle boolean,
  sort_order smallint not null default 0
);

create table public.announcements (
  id uuid primary key default gen_random_uuid(),
  body_fr text not null,
  body_en text not null,
  published_at timestamptz not null default now(),
  author_role text not null check (author_role in ('admin','regie'))
);

-- ---------------------------------------------------------------- Médias
create table public.media (
  id uuid primary key default gen_random_uuid(),
  storage_path text not null unique,
  household_id uuid references public.households(id) on delete set null,
  moment_id text references public.moments(id),
  kind text not null check (kind in ('photo','video')),
  mime text not null,
  bytes bigint not null check (bytes > 0),
  width integer,
  height integer,
  duration_s numeric(6,2) check (duration_s is null or duration_s <= 60),
  status text not null default 'pending' check (status in ('pending','published','hidden')),
  gps_stripped boolean not null default false,
  created_at timestamptz not null default now()
);
create index on public.media (status, created_at desc);
create index on public.media (moment_id);

create table public.media_takedown (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media(id) on delete cascade,
  requester_household_id uuid references public.households(id) on delete set null,
  reason text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

-- « J'aime » privé : sert uniquement au tri, jamais affiché en nombre (§17).
create table public.media_signal (
  media_id uuid not null references public.media(id) on delete cascade,
  household_id uuid not null references public.households(id) on delete cascade,
  primary key (media_id, household_id)
);

create table public.photo_challenges (
  id uuid primary key default gen_random_uuid(),
  moment_id text not null references public.moments(id),
  title_fr text not null,
  title_en text not null,
  published boolean not null default false
);

-- ---------------------------------------------------------------- Autour
-- La promesse : chiffré côté navigateur, illisible du serveur et des mariés
-- jusqu'au 3 juin 2029. Aucune politique de lecture n'existe (voir RLS).
create table public.promises (
  id uuid primary key default gen_random_uuid(),
  ciphertext text not null,
  created_at timestamptz not null default now(),
  sealed_until date not null default date '2029-06-03'
    check (sealed_until = date '2029-06-03'),
  remise_le timestamptz
);

create table public.absent_messages (
  id uuid primary key default gen_random_uuid(),
  household_id uuid references public.households(id) on delete set null,
  body text not null,
  visibility text not null default 'private' check (visibility in ('guestbook','private')),
  created_at timestamptz not null default now()
);

create table public.seating_tables (
  id uuid primary key default gen_random_uuid(),
  label text not null unique,
  capacity smallint check (capacity > 0),
  sort_order smallint not null default 0
);

create table public.seating_assign (
  guest_id uuid primary key references public.guests(id) on delete cascade,
  table_id uuid not null references public.seating_tables(id) on delete cascade
);

create table public.admin_users (
  email text primary key,
  user_id uuid unique,                            -- rempli à la première connexion
  role text not null check (role in ('admin','regie','tech')),
  invited_at timestamptz not null default now(),
  last_seen_at timestamptz,
  revoked_at timestamptz
);

-- Journal sans donnée personnelle (§11) : ni nom, ni e-mail, ni contenu.
create table public.audit_log (
  id bigserial primary key,
  actor uuid,
  role text,
  action text not null,
  target text,
  at timestamptz not null default now()
);
create index on public.audit_log (at desc);
