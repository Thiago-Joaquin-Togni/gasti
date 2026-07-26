import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from core.LoggerManagger import log


class DAO:
    def __init__(self):
        self.conn = None
        self._connect()

    def _connect(self):
        self.conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
        )
        self.conn.autocommit = True
        log.info("Conexión a PostgreSQL establecida.")

    def _ensure_connection(self):
        if not self.conn or self.conn.closed:
            log.warning("Conexión perdida. Reconectando...")
            self._connect()

    def _execute(self, query, params=None):
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute(query, params)

    def _fetchone(self, query, params=None):
        self._ensure_connection()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _fetchall(self, query, params=None):
        self._ensure_connection()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    # ── Usuarios ──

    def registrar_usuario(self, id_telegram: str, username: str = None) -> dict:
        self._execute("CALL sp_registrar_usuario(%s, %s)", (id_telegram, username))
        log.info(f"Usuario registrado/actualizado: {id_telegram}")
        return self.obtener_usuario(id_telegram)

    def obtener_usuario(self, id_telegram: str) -> dict | None:
        return self._fetchone(
            "SELECT * FROM fn_obtener_usuario(%s)", (id_telegram,)
        )

    # ── Categorías ──

    def listar_categorias(self) -> list[dict]:
        return self._fetchall("SELECT * FROM fn_listar_categorias()")

    def obtener_categoria_por_nombre(self, nombre: str) -> dict | None:
        return self._fetchone(
            "SELECT * FROM fn_obtener_categoria_por_nombre(%s)", (nombre,)
        )

    def obtener_categoria_por_id(self, categoria_id: int) -> dict | None:
        return self._fetchone(
            "SELECT * FROM fn_obtener_categoria_por_id(%s)", (categoria_id,)
        )

    # ── Registros ──

    def insertar_registro(
        self,
        id_telegram: str,
        monto: float,
        descripcion: str,
        tipo: str,
        categoria_id: int = None,
    ) -> int:
        registro_id = self._fetchone(
            "SELECT fn_insertar_registro(%s, %s, %s, %s, %s)",
            (id_telegram, monto, descripcion, tipo, categoria_id),
        )
        nuevo_id = registro_id["fn_insertar_registro"] if registro_id else None
        log.info(
            f"Registro insertado: id={nuevo_id}, tipo={tipo}, "
            f"monto={monto}, usuario={id_telegram}"
        )
        return nuevo_id

    def listar_registros(
        self, id_telegram: str, limite: int = 50, offset: int = 0
    ) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM fn_listar_registros(%s, %s, %s)",
            (id_telegram, limite, offset),
        )

    def obtener_registro_por_id(self, registro_id: int) -> dict | None:
        return self._fetchone(
            "SELECT * FROM fn_obtener_registro_por_id(%s)", (registro_id,)
        )

    def listar_registros_pendientes(self, id_telegram: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM fn_listar_registros_pendientes(%s)", (id_telegram,)
        )

    def actualizar_estado_registro(self, registro_id: int, estado: str) -> None:
        self._execute(
            "SELECT fn_actualizar_estado_registro(%s, %s)", (registro_id, estado)
        )
        log.info(f"Estado de registro {registro_id} actualizado a {estado}")

    # ── Lifecycle ──

    def cerrar(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
            log.info("Conexión a PostgreSQL cerrada.")
