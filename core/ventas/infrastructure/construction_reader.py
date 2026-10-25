# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional reader of legacy construction data. Never imports core.database."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from ..domain.errors import StorageError, ValidationError


class ConstructionRepository:
    def __init__(self, path, user_id=None, is_admin=False):
        self.path, self.user_id, self.is_admin = Path(path), user_id, is_admin

    @contextmanager
    def read(self):
        connection = None
        try:
            connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            yield connection
        except sqlite3.Error as exc:
            raise StorageError('Construcción no disponible o esquema incompatible para lectura. Puede seguir cotizando sin el conector.') from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def columns(connection, table):
        if table not in ('proyectos', 'partidas', 'recursos', 'acu_items', 'configuracion'):
            raise ValidationError('Tabla no admitida por el lector de Construcción.')
        return {row['name'] for row in connection.execute(f'PRAGMA table_info({table})')}

    def scope(self, columns):
        if self.user_id is not None and not self.is_admin and 'usuario_id' in columns:
            return ' AND (usuario_id=? OR usuario_id IS NULL)', [self.user_id]
        return '', []

    def project(self, connection, project_id):
        columns = self.columns(connection, 'proyectos')
        if not {'id', 'nombre', 'moneda'} <= columns:
            raise ValidationError('Proyecto sin identificación/moneda compatible; no se puede importar.')
        clause, params = self.scope(columns)
        row = connection.execute('SELECT id,nombre,moneda FROM proyectos WHERE id=?' + clause, [project_id] + params).fetchone()
        if row is None:
            raise ValidationError('Proyecto no encontrado o no autorizado para esta sesión.')
        return dict(row)

    def projects(self):
        with self.read() as connection:
            columns = self.columns(connection, 'proyectos')
            if not {'id', 'nombre', 'moneda'} <= columns:
                raise ValidationError('No hay esquema de proyectos compatible. Ventas sigue disponible sin importación.')
            clause, params = self.scope(columns)
            return [dict(row) for row in connection.execute('SELECT id,nombre,moneda FROM proyectos WHERE 1=1' + clause + ' ORDER BY nombre COLLATE NOCASE LIMIT 2000', params)]

    def parts(self, project_id, search=''):
        with self.read() as connection:
            self.project(connection, project_id)
            return [dict(row) for row in connection.execute(
                'SELECT id,item,descripcion,unidad,CAST(metrado AS TEXT) quantity,CAST(precio_unitario AS TEXT) cost FROM partidas WHERE proyecto_id=? AND es_titulo=0 AND (descripcion LIKE ? OR item LIKE ?) ORDER BY item,id LIMIT 5000',
                (project_id, '%' + search + '%', '%' + search + '%'))]

    def snapshot_data(self, project_id, partida_id):
        with self.read() as connection:
            project = self.project(connection, project_id)
            columns = self.columns(connection, 'partidas')
            required = {'id', 'proyecto_id', 'item', 'descripcion', 'unidad', 'metrado', 'precio_unitario', 'es_titulo'}
            if not required <= columns:
                raise ValidationError('Esquema de partidas no compatible con el lector.')
            fields = 'id,proyecto_id,item,descripcion,unidad,es_titulo,CAST(metrado AS TEXT) metrado,CAST(precio_unitario AS TEXT) precio_unitario'
            if 'rendimiento' in columns:
                fields += ',CAST(rendimiento AS TEXT) rendimiento'
            part = connection.execute('SELECT ' + fields + ' FROM partidas WHERE id=? AND proyecto_id=?', (partida_id, project_id)).fetchone()
            if part is None or part['es_titulo']:
                raise ValidationError('Seleccione una partida cotizable que pertenezca al proyecto, no un agrupador.')
            ai_columns = self.columns(connection, 'acu_items')
            resource_columns = self.columns(connection, 'recursos')
            if not {'id', 'partida_id', 'recurso_id', 'cantidad', 'cuadrilla'} <= ai_columns or not {'id', 'codigo', 'descripcion', 'tipo', 'unidad', 'precio'} <= resource_columns:
                raise ValidationError('Desglose ACU no compatible; no se generará una copia incompleta.')
            override = 'ai.precio' if 'precio' in ai_columns else 'NULL'
            query = ('SELECT ai.id,ai.recurso_id,CAST(ai.cuadrilla AS TEXT) cuadrilla,CAST(ai.cantidad AS TEXT) cantidad,'
                     'r.codigo,r.descripcion,r.tipo,r.unidad,CAST(r.precio AS TEXT) precio_catalogo,'
                     f'CAST({override} AS TEXT) precio_proyecto,CAST(COALESCE({override},r.precio) AS TEXT) precio_efectivo '
                     'FROM acu_items ai LEFT JOIN recursos r ON r.id=ai.recurso_id WHERE ai.partida_id=? ORDER BY ai.id')
            items = [dict(row) for row in connection.execute(query, (partida_id,))]
            if any(item['descripcion'] is None for item in items):
                raise ValidationError('ACU con referencias de recursos incompletas; revise la obra antes de importar.')
            configuration = {}
            if {'clave', 'valor'} <= self.columns(connection, 'configuracion'):
                for row in connection.execute("SELECT clave,valor FROM configuracion WHERE clave IN ('decimales_presupuesto','decimales_metrado','decimales_cantidad_mo','decimales_cantidad_mat','decimales_cantidad_eq','decimales_cantidad_sc') ORDER BY clave"):
                    configuration[row['clave']] = row['valor']
            project_columns = self.columns(connection, 'proyectos')
            context_fields = [name for name in ('costo_al', 'modificado_en', 'jornada_laboral', 'estado') if name in project_columns]
            if context_fields:
                # Names above are a fixed whitelist. Legacy REALs cross as SQLite TEXT.
                row = connection.execute('SELECT ' + ','.join('CAST(' + name + ' AS TEXT) ' + name for name in context_fields) + ' FROM proyectos WHERE id=?', (project_id,)).fetchone()
                project.update(dict(row))
            return {'project': project, 'partida': dict(part), 'acu_items': items, 'configuration': configuration,
                    'price_rule': 'partidas.precio_unitario almacenado; ACU COALESCE(ai.precio,recursos.precio); sin recalcular'}
