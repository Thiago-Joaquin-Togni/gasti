-- Active: 1783640823710@@localhost@5433@gasti_dev
-- ==========================================
-- 1. USUARIOS
-- ==========================================

-- SP para registrar o actualizar un usuario (Escritura)
CREATE OR REPLACE PROCEDURE sp_registrar_usuario(
    p_id_telegram VARCHAR(100),
    p_username VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO usuarios (id_telegram, username)
    VALUES (p_id_telegram, p_username)
    ON CONFLICT (id_telegram)
    DO UPDATE SET username = EXCLUDED.username;
END;
$$;

-- Función para obtener un usuario por su ID de Telegram (Lectura)
CREATE OR REPLACE FUNCTION fn_obtener_usuario(p_id_telegram VARCHAR(100))
RETURNS TABLE (
    id_telegram VARCHAR(100),
    username VARCHAR(100),
    fecha_registro TIMESTAMP
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT u.id_telegram, u.username, u.fecha_registro
    FROM usuarios u
    WHERE u.id_telegram = p_id_telegram;
END;
$$;


-- ==========================================
-- 2. CATEGORÍAS
-- ==========================================

-- Función para listar todas las categorías ordenadas por nombre (Lectura)
CREATE OR REPLACE FUNCTION fn_listar_categorias()
RETURNS TABLE (
    id INT,
    nombre VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.nombre
    FROM categorias c
    ORDER BY c.nombre;
END;
$$;

-- Función para obtener categoría por su nombre (Lectura)
CREATE OR REPLACE FUNCTION fn_obtener_categoria_por_nombre(p_nombre VARCHAR(100))
RETURNS TABLE (
    id INT,
    nombre VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.nombre
    FROM categorias c
    WHERE c.nombre = p_nombre;
END;
$$;

-- Función para obtener categoría por su ID (Lectura)
CREATE OR REPLACE FUNCTION fn_obtener_categoria_por_id(p_categoria_id INT)
RETURNS TABLE (
    id INT,
    nombre VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.nombre
    FROM categorias c
    WHERE c.id = p_categoria_id;
END;
$$;


-- ==========================================
-- 3. REGISTROS
-- ==========================================

-- Función para insertar un nuevo registro devolviendo el ID generado (Escritura)
CREATE OR REPLACE FUNCTION fn_insertar_registro(
    p_id_telegram VARCHAR(100),
    p_monto NUMERIC,
    p_descripcion TEXT,
    p_tipo VARCHAR(20),
    p_categoria_id INT DEFAULT NULL
) RETURNS INT AS $$
DECLARE
    v_id INT;
BEGIN
    INSERT INTO registros (id_telegram, monto, descripcion, tipo, categoria_id)
    VALUES (p_id_telegram, p_monto, p_descripcion, p_tipo, p_categoria_id)
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar el estado de un registro (Escritura)
CREATE OR REPLACE FUNCTION fn_actualizar_estado_registro(
    p_registro_id INT,
    p_estado VARCHAR(20)
) RETURNS VOID AS $$
BEGIN
    UPDATE registros SET estado = p_estado::registro_estado_enum WHERE id = p_registro_id;
END;
$$ LANGUAGE plpgsql;

-- Función para listar los registros de un usuario con su categoría (Lectura)
CREATE OR REPLACE FUNCTION fn_listar_registros(
    p_id_telegram VARCHAR(100),
    p_limite INT DEFAULT 50,
    p_offset INT DEFAULT 0
)
RETURNS TABLE (
    id INT,
    id_telegram VARCHAR(100),
    monto NUMERIC,
    descripcion TEXT,
    tipo VARCHAR(20),
    categoria_id INT,
    fecha_hora TIMESTAMP,
    categoria_nombre VARCHAR(100),
    estado VARCHAR(20)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        r.id_telegram,
        r.monto,
        r.descripcion,
        r.tipo,
        r.categoria_id,
        r.fecha_hora,
        c.nombre AS categoria_nombre,
        r.estado::VARCHAR AS estado
    FROM registros r
    LEFT JOIN categorias c ON r.categoria_id = c.id
    WHERE r.id_telegram = p_id_telegram
    ORDER BY r.fecha_hora DESC
    LIMIT p_limite OFFSET p_offset;
END;
$$;

-- Función para obtener un registro específico por su ID (Lectura)
CREATE OR REPLACE FUNCTION fn_obtener_registro_por_id(p_registro_id INT)
RETURNS TABLE (
    id INT,
    id_telegram VARCHAR(100),
    monto NUMERIC,
    descripcion TEXT,
    tipo VARCHAR(20),
    categoria_id INT,
    fecha_hora TIMESTAMP,
    categoria_nombre VARCHAR(100),
    estado VARCHAR(20)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        r.id_telegram,
        r.monto,
        r.descripcion,
        r.tipo,
        r.categoria_id,
        r.fecha_hora,
        c.nombre AS categoria_nombre,
        r.estado::VARCHAR AS estado
    FROM registros r
    LEFT JOIN categorias c ON r.categoria_id = c.id
    WHERE r.id = p_registro_id;
END;
$$;

-- Función para listar registros pendientes de un usuario (Lectura)
CREATE OR REPLACE FUNCTION fn_listar_registros_pendientes(
    p_id_telegram VARCHAR(100)
)
RETURNS TABLE (
    id INT,
    monto NUMERIC,
    descripcion TEXT,
    tipo VARCHAR(20),
    fecha_hora TIMESTAMP
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        r.monto,
        r.descripcion,
        r.tipo,
        r.fecha_hora
    FROM registros r
    WHERE r.id_telegram = p_id_telegram
      AND r.estado = 'PENDIENTE'
    ORDER BY r.fecha_hora DESC;
END;
$$;
