import '../models/customer.dart';
import '../utils/parsing.dart';
import 'base_dao.dart';

class CustomerDao extends BaseDao<Customer> {
  @override
  String get tableName => 'customers';

  @override
  String get defaultOrder => 'name COLLATE NOCASE ASC';

  @override
  Map<String, Object?> toMap(Customer c) => {
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'address': c.address,
        'notes': c.notes,
        'is_active': c.isActive ? 1 : 0,
        'created_at': c.createdAt.toUtc().toIso8601String(),
        'total_credit': c.totalCredit,
        'total_paid': c.totalPaid,
      };

  @override
  Customer fromMap(Map<String, Object?> map) => Customer(
        id: map['id'] as String,
        name: map['name'] as String,
        phone: map['phone'] as String?,
        address: map['address'] as String?,
        notes: map['notes'] as String?,
        isActive: (map['is_active'] as int? ?? 1) == 1,
        createdAt: parseServerDate(map['created_at']),
        totalCredit: map['total_credit'] as int? ?? 0,
        totalPaid: map['total_paid'] as int? ?? 0,
      );
}
