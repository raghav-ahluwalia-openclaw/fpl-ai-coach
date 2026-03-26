"""Initial schema - FPL AI Coach database structure

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-03-26 00:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('short_name', sa.String(length=50), nullable=True),
        sa.Column('strength', sa.Integer(), nullable=True),
        sa.Column('strength_overall_home', sa.Integer(), nullable=True),
        sa.Column('strength_overall_away', sa.Integer(), nullable=True),
        sa.Column('strength_attack_home', sa.Integer(), nullable=True),
        sa.Column('strength_attack_away', sa.Integer(), nullable=True),
        sa.Column('strength_defence_home', sa.Integer(), nullable=True),
        sa.Column('strength_defence_away', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teams_code'), 'teams', ['code'], unique=False)
    
    # Create players table
    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('element_id', sa.Integer(), nullable=True),
        sa.Column('web_name', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('second_name', sa.String(length=100), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('element_type', sa.Integer(), nullable=True),
        sa.Column('now_cost', sa.Integer(), nullable=True),
        sa.Column('total_points', sa.Integer(), nullable=True),
        sa.Column('points_per_game', sa.String(length=20), nullable=True),
        sa.Column('form', sa.String(length=20), nullable=True),
        sa.Column('selected_by_percent', sa.String(length=20), nullable=True),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('goals_scored', sa.Integer(), nullable=True),
        sa.Column('assists', sa.Integer(), nullable=True),
        sa.Column('clean_sheets', sa.Integer(), nullable=True),
        sa.Column('goals_conceded', sa.Integer(), nullable=True),
        sa.Column('own_goals', sa.Integer(), nullable=True),
        sa.Column('penalties_saved', sa.Integer(), nullable=True),
        sa.Column('penalties_missed', sa.Integer(), nullable=True),
        sa.Column('yellow_cards', sa.Integer(), nullable=True),
        sa.Column('red_cards', sa.Integer(), nullable=True),
        sa.Column('saves', sa.Integer(), nullable=True),
        sa.Column('bonus', sa.Integer(), nullable=True),
        sa.Column('bps', sa.Integer(), nullable=True),
        sa.Column('influence', sa.String(length=20), nullable=True),
        sa.Column('creativity', sa.String(length=20), nullable=True),
        sa.Column('threat', sa.String(length=20), nullable=True),
        sa.Column('ict_index', sa.String(length=20), nullable=True),
        sa.Column('chance_of_playing_next_round', sa.Integer(), nullable=True),
        sa.Column('chance_of_playing_this_round', sa.Integer(), nullable=True),
        sa.Column('news', sa.String(length=500), nullable=True),
        sa.Column('news_added', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('in_dreamteam', sa.Boolean(), nullable=True),
        sa.Column('dreamteam_count', sa.Integer(), nullable=True),
        sa.Column('value_form', sa.String(length=20), nullable=True),
        sa.Column('value_season', sa.String(length=20), nullable=True),
        sa.Column('transfers_in', sa.Integer(), nullable=True),
        sa.Column('transfers_out', sa.Integer(), nullable=True),
        sa.Column('transfers_in_event', sa.Integer(), nullable=True),
        sa.Column('transfers_out_event', sa.Integer(), nullable=True),
        sa.Column('cost_change_start', sa.Integer(), nullable=True),
        sa.Column('cost_change_event', sa.Integer(), nullable=True),
        sa.Column('cost_change_start_fall', sa.Integer(), nullable=True),
        sa.Column('cost_change_event_fall', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_players_element_id'), 'players', ['element_id'], unique=False)
    op.create_index(op.f('ix_players_team_id'), 'players', ['team_id'], unique=False)
    op.create_index(op.f('ix_players_element_type'), 'players', ['element_type'], unique=False)
    
    # Create fixtures table
    op.create_table(
        'fixtures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Integer(), nullable=True),
        sa.Column('event', sa.Integer(), nullable=True),
        sa.Column('finished', sa.Boolean(), nullable=True),
        sa.Column('finished_provisional', sa.Boolean(), nullable=True),
        sa.Column('kickoff_time', sa.String(length=50), nullable=True),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('provisional_start_time', sa.Boolean(), nullable=True),
        sa.Column('started', sa.Boolean(), nullable=True),
        sa.Column('team_a', sa.Integer(), nullable=True),
        sa.Column('team_a_score', sa.Integer(), nullable=True),
        sa.Column('team_h', sa.Integer(), nullable=True),
        sa.Column('team_h_score', sa.Integer(), nullable=True),
        sa.Column('team_h_difficulty', sa.Integer(), nullable=True),
        sa.Column('team_a_difficulty', sa.Integer(), nullable=True),
        sa.Column('pulse_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['team_a'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['team_h'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fixtures_event'), 'fixtures', ['event'], unique=False)
    op.create_index(op.f('ix_fixtures_team_h'), 'fixtures', ['team_h'], unique=False)
    op.create_index(op.f('ix_fixtures_team_a'), 'fixtures', ['team_a'], unique=False)
    
    # Create meta table for application metadata
    op.create_table(
        'meta',
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=1000), nullable=True),
        sa.Column('updated_at', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )
    
    # Create user_squad_picks table for tracking user teams
    op.create_table(
        'user_squad_picks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=True),
        sa.Column('event', sa.Integer(), nullable=True),
        sa.Column('player_id', sa.Integer(), nullable=True),
        sa.Column('list_position', sa.Integer(), nullable=True),
        sa.Column('multiplier', sa.Integer(), nullable=True),
        sa.Column('is_captain', sa.Boolean(), nullable=True),
        sa.Column('is_vice_captain', sa.Boolean(), nullable=True),
        sa.Column('purchase_price', sa.Integer(), nullable=True),
        sa.Column('selling_price', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_squad_picks_entry_id'), 'user_squad_picks', ['entry_id'], unique=False)
    op.create_index(op.f('ix_user_squad_picks_event'), 'user_squad_picks', ['event'], unique=False)
    op.create_index(op.f('ix_user_squad_picks_player_id'), 'user_squad_picks', ['player_id'], unique=False)

    # Create player_predictions table for Pro features (Drift Analysis)
    op.create_table(
        'player_predictions',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('event', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('xp_1gw', sa.Float(), nullable=False),
        sa.Column('xp_3gw', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(length=100), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('actual_points', sa.Integer(), nullable=True),
        sa.Column('prediction_error', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_player_predictions_event_player'), 'player_predictions', ['event', 'player_id'], unique=False)
    op.create_index(op.f('ix_player_predictions_created_at'), 'player_predictions', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_player_predictions_created_at'), table_name='player_predictions')
    op.drop_index(op.f('ix_player_predictions_event_player'), table_name='player_predictions')
    op.drop_table('player_predictions')
    op.drop_index(op.f('ix_user_squad_picks_player_id'), table_name='user_squad_picks')
    op.drop_index(op.f('ix_user_squad_picks_event'), table_name='user_squad_picks')
    op.drop_index(op.f('ix_user_squad_picks_entry_id'), table_name='user_squad_picks')
    op.drop_table('user_squad_picks')
    op.drop_table('meta')
    op.drop_index(op.f('ix_fixtures_team_a'), table_name='fixtures')
    op.drop_index(op.f('ix_fixtures_team_h'), table_name='fixtures')
    op.drop_index(op.f('ix_fixtures_event'), table_name='fixtures')
    op.drop_table('fixtures')
    op.drop_index(op.f('ix_players_element_type'), table_name='players')
    op.drop_index(op.f('ix_players_team_id'), table_name='players')
    op.drop_index(op.f('ix_players_element_id'), table_name='players')
    op.drop_table('players')
    op.drop_index(op.f('ix_teams_code'), table_name='teams')
    op.drop_table('teams')
