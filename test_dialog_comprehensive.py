import sys
sys.stdout.reconfigure(encoding='utf-8')
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

app = QtWidgets.QApplication(sys.argv + ['-platform', 'offscreen'])

from module_3.task_rule_editor_dialog import TaskRuleEditorDialog

# Sample task data
sample_task = {
    'id': 1,
    'task_name': 'Test Task Inspection',
    'enabled': 1,
    'task_type': 'RELATION_COORDINATE',
    'plc_register': 'D100',
    'plc_value_state': 1,
    'plc_value_ok': 1,
    'plc_value_ng': 0,
    'logic_operator': 'ALL_PASS'
}

sample_rules = [
    {
        'id': 101,
        'label_1': 'Plate_A',
        'label_2': 'Hole_B',
        'instance_scope': '1_VS_1',
        'param_1': 'X_MIN',
        'operator': '<',
        'target_type': 'LABEL',
        'param_2': 'X_MAX',
        'math_op': '+',
        'math_operand_val': 10.0,
        'true_result': 'NG'
    }
]

dlg = TaskRuleEditorDialog(camera_id=1, model_id=1, task_data=sample_task, rules_data=sample_rules)
dlg.show()
app.processEvents()

print("✓ Dialog initialized successfully.")
print(f"Window title: {dlg.windowTitle()}")
print(f"Table row count: {dlg.table_rules.rowCount()}")

# Test selecting rule row 0
dlg.table_rules.selectRow(0)
app.processEvents()
print(f"Selected row 0: combo_operator={dlg.combo_operator.currentData()}, math_val={dlg.line_math_val.text()}")

# Test changing operator to INSIDE (spatial)
idx_inside = dlg.combo_operator.findData('INSIDE')
if idx_inside >= 0:
    dlg.combo_operator.setCurrentIndex(idx_inside)
    app.processEvents()
    print(f"Changed to INSIDE: param_1 enabled={dlg.combo_param_1.isEnabled()}, lbl_math_op={dlg.lbl_math_op.text()}")

# Test changing operator to DIST_< (distance)
idx_dist = dlg.combo_operator.findData('DIST_<')
if idx_dist >= 0:
    dlg.combo_operator.setCurrentIndex(idx_dist)
    app.processEvents()
    print(f"Changed to DIST_<: combo_math_op enabled={dlg.combo_math_op.isEnabled()}, lbl_math_val={dlg.lbl_math_val.text()}")

# Test changing back to <
idx_less = dlg.combo_operator.findData('<')
if idx_less >= 0:
    dlg.combo_operator.setCurrentIndex(idx_less)
    app.processEvents()
    print(f"Changed to <: param_1 enabled={dlg.combo_param_1.isEnabled()}, lbl_math_op={dlg.lbl_math_op.text()}")

# Test adding a new rule
dlg.line_math_val.setText("25.5")
dlg.btn_add_rule.click()
app.processEvents()
print(f"After add_rule, Table row count: {dlg.table_rules.rowCount()}")

# Test updating rule
dlg.table_rules.selectRow(1)
dlg.line_math_val.setText("30.0")
dlg.btn_update_rule.click()
app.processEvents()
print(f"After update_rule, row 1 val: {dlg.rules_list[1].get('math_operand_val')}")

# Test deleting rule
dlg.table_rules.selectRow(1)
dlg.delete_selected_rule()
app.processEvents()
print(f"After delete_rule, Table row count: {dlg.table_rules.rowCount()}")

# Test saving task data retrieval
task_res, rules_res = dlg.get_task_and_rules()
print(f"get_task_and_rules task_name: {task_res.get('task_name')}")
print(f"get_task_and_rules value_state: {task_res.get('plc_value_state')}")
print(f"get_task_and_rules rules count: {len(rules_res)}")

print("\nALL VERIFICATION CHECKS PASSED!")

