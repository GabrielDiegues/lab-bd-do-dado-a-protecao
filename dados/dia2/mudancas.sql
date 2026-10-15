-- Mudanças do dia 2, aplicadas na origem nesta ordem.
UPDATE pedidos SET status = 'pago', atualizado_em = '2026-10-02T08:10:00' WHERE id = 105;
UPDATE clientes SET email = 'carla.n@example.com', atualizado_em = '2026-10-02T08:20:00' WHERE id = 3;
INSERT INTO clientes (id, nome, email, cpf, nascimento, cidade, atualizado_em)
  VALUES (7, 'Gabi Rocha', 'gabi.rocha@example.com', '777.777.777-77', '1996-02-25', 'Sorocaba', '2026-10-02T08:30:00');
INSERT INTO pedidos (id, cliente_id, valor_centavos, status, criado_em, atualizado_em, observacao)
  VALUES (109, 7, 5600, 'pago', '2026-10-02T08:40:00', '2026-10-02T08:40:00', NULL);
DELETE FROM clientes WHERE id = 5;
