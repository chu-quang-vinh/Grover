# thang_grover/grover_builder.py


from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
import numpy as np
# Giả sử diffuser.py nằm cùng thư mục và có hàm build_diffuser
try:
    from diffuser import build_diffuser # Import hàm từ Nhiệm vụ 1
except ModuleNotFoundError:
    print("CẢNH BÁO: Không tìm thấy file diffuser.py hoặc hàm build_diffuser.")
    print("Hàm build_grover_circuit sẽ không hoạt động đúng nếu không có build_diffuser.")
    # Định nghĩa một hàm build_diffuser giả để code không lỗi ngay lập tức khi import
    def build_diffuser(n_qubits: int) -> QuantumCircuit:
        print(f"CẢNH BÁO: Đang dùng build_diffuser giả cho {n_qubits} qubits.")
        return QuantumCircuit(n_qubits, name=f"DummyDiffuser_{n_qubits}q")

# --- HÀM TẠO MOCK ORACLE PHỨC TẠP HƠN ---
def create_complex_mock_oracle(
        n_search_qubits: int, 
        num_oracle_ancillas: int, # Số qubit phụ trợ Oracle này sẽ dùng
        mark_state_str: str, # Chuỗi bit (MSB-first) của trạng thái cần đánh dấu
        # Thêm các tham số khác nếu bạn muốn oracle phức tạp hơn nữa
        # ví dụ: condition_on_other_ancillas: list = None 
    ) -> QuantumCircuit:
    """
    Tạo một mock oracle có thể tùy chỉnh cho mục đích benchmark và kiểm thử.
    Oracle này sử dụng (n_search_qubits + num_oracle_ancillas) qubit tổng cộng.
    Một trong các ancilla (ancilla đầu tiên) được dùng để đảo pha.
    Nó sẽ đánh dấu trạng thái được chỉ định bởi `mark_state_str`.

    Args:
        n_search_qubits: Số qubit của không gian tìm kiếm.
        num_oracle_ancillas: Số qubit phụ trợ mà Oracle này sẽ sử dụng. Phải >= 1.
        mark_state_str: Chuỗi bit (MSB-first) của trạng thái cần đánh dấu.
                        Độ dài phải bằng n_search_qubits.

    Returns:
        QuantumCircuit: Mạch Oracle.
    """
    if len(mark_state_str) != n_search_qubits:
        raise ValueError("Độ dài của mark_state_str phải bằng n_search_qubits.")
    if num_oracle_ancillas < 1:
        # Cần ít nhất 1 qubit phụ trợ cho result_qubit để thực hiện phase kickback.
        # Các ancilla khác có thể cần cho việc phân rã MCX nếu n_search_qubits lớn.
        raise ValueError("Cần ít nhất 1 qubit phụ trợ cho Oracle.")

    num_oracle_total_qubits = n_search_qubits + num_oracle_ancillas
    oracle_qc = QuantumCircuit(num_oracle_total_qubits, name=f"ComplexOracle_{n_search_qubits}s+{num_oracle_ancillas}a")

    search_indices = list(range(n_search_qubits))
    # Qubit phụ trợ đầu tiên trong số các ancilla của Oracle được dùng làm result_qubit
    result_qubit_oracle_local_idx = n_search_qubits 
    
    # Các qubit phụ trợ còn lại (nếu có) có thể dùng cho MCX
    mcx_ancilla_oracle_local_indices = list(range(n_search_qubits + 1, num_oracle_total_qubits))

    # ---- LOGIC ORACLE: Đánh dấu target_key_to_mark_str ----
    # 1. Áp dụng X nếu bit trong target_key là '0' để chuẩn bị cho MCX
    for i in range(n_search_qubits):
        qubit_in_search_space = search_indices[i] # q_i
        # Ánh xạ đúng: q_N-1 (MSB của không gian khóa) ứng với target_key_to_mark_str[0]
        # q_i ứng với target_key_to_mark_str[ (n_search_qubits - 1) - i ]
        char_to_match = mark_state_str[(n_search_qubits - 1) - i]
        if char_to_match == '0':
            oracle_qc.x(qubit_in_search_space)
    
    # 2. Lật bit result_qubit_oracle_local_idx nếu tất cả key_qubits_indices khớp
    if n_search_qubits > 0:
        chosen_mcx_mode = 'recursion' # Nên dùng 'recursion' hoặc 'v-chain' cho nhiều control
        if n_search_qubits <= 2: # 1 hoặc 2 control
            chosen_mcx_mode = 'noancilla'
        elif not mcx_ancilla_oracle_local_indices and n_search_qubits > 2 : # Cần ancilla nhưng không có
             print(f"    Cảnh báo Oracle: MCX với {n_search_qubits} control qubits có thể cần ancilla tường minh "
                   f"(hiện không có ancilla phụ cho MCX được cung cấp).")
             # Qiskit có thể cố gắng dùng dirty ancilla hoặc phân rã sâu.
        
        oracle_qc.mcx(search_indices, result_qubit_oracle_local_idx,
                      ancilla_qubits=mcx_ancilla_oracle_local_indices if mcx_ancilla_oracle_local_indices else None,
                      mode=chosen_mcx_mode)

    # 3. Hoàn tác X gates ở bước 1
    for i in range(n_search_qubits):
        qubit_in_search_space = search_indices[i]
        char_to_match = mark_state_str[(n_search_qubits - 1) - i]
        if char_to_match == '0':
            oracle_qc.x(qubit_in_search_space)
    # ---- KẾT THÚC PHẦN TÍNH TOÁN ----

    oracle_qc.z(result_qubit_oracle_local_idx) # Đảo pha nếu result_qubit là |1>

    # ---- UNCOMPUTATION ----
    # Hoàn tác các bước tính toán để result_qubit_oracle_local_idx trở về |0>
    for i in range(n_search_qubits):
        qubit_in_search_space = search_indices[i]
        char_to_match = mark_state_str[(n_search_qubits - 1) - i]
        if char_to_match == '0':
            oracle_qc.x(qubit_in_search_space)
            
    if n_search_qubits > 0:
        chosen_mcx_mode_uncompute = 'recursion'
        if n_search_qubits <= 2:
            chosen_mcx_mode_uncompute = 'noancilla'
        
        oracle_qc.mcx(search_indices, result_qubit_oracle_local_idx,
                      ancilla_qubits=mcx_ancilla_oracle_local_indices if mcx_ancilla_oracle_local_indices else None,
                      mode=chosen_mcx_mode_uncompute)
               
    for i in range(n_search_qubits):
        qubit_in_search_space = search_indices[i]
        char_to_match = mark_state_str[(n_search_qubits - 1) - i]
        if char_to_match == '0':
            oracle_qc.x(qubit_in_search_space)
            
    return oracle_qc


def build_grover_circuit(n_qubits: int, 
                         iterations: int, 
                         oracle_circuit: QuantumCircuit) -> QuantumCircuit:
    """
    Xây dựng mạch thuật toán Grover hoàn chỉnh.
    """
    if not isinstance(n_qubits, int) or n_qubits < 1:
        raise ValueError("n_qubits phải là một số nguyên dương.")
    if not isinstance(iterations, int) or iterations < 0:
        raise ValueError("iterations phải là một số nguyên không âm.")
    if not isinstance(oracle_circuit, QuantumCircuit):
        raise ValueError("oracle_circuit phải là một đối tượng QuantumCircuit.")
    
    total_circuit_qubits = oracle_circuit.num_qubits
    
    if n_qubits > total_circuit_qubits:
        raise ValueError(f"Số qubit tìm kiếm (n_qubits={n_qubits}) "
                         f"không thể lớn hơn tổng số qubit của oracle_circuit ({total_circuit_qubits}).")

    grover_qc = QuantumCircuit(total_circuit_qubits, name="GroverCircuit")
    search_qubit_indices = list(range(n_qubits))

    for qubit_idx in search_qubit_indices:
        grover_qc.h(qubit_idx)
    grover_qc.barrier(label="Init_H")

    diffuser_for_search_space = build_diffuser(n_qubits) 

    for i in range(iterations):
        qubits_for_oracle = list(range(oracle_circuit.num_qubits))
        grover_qc.compose(oracle_circuit, qubits=qubits_for_oracle, inplace=True)
        grover_qc.barrier(label=f"Oracle_{i+1}")

        grover_qc.compose(diffuser_for_search_space, qubits=search_qubit_indices, inplace=True)
        grover_qc.barrier(label=f"Diffuser_{i+1}")
        
    return grover_qc

if __name__ == '__main__':
    print("--- Chạy kiểm thử cục bộ cho grover_builder.py ---")
    
    # Kịch bản 1: Sử dụng Oracle phức tạp hơn (ví dụ 4 qubit tìm kiếm, 2 ancilla)
    n_search_q1 = 4
    num_ancillas_oracle1 = 2 # 1 cho result_qubit, 1 cho mcx nếu cần (mcx(4 control) có thể cần)
    target_key1_str = "1010" # MSB-first: q3=1, q2=0, q1=1, q0=0

    print(f"\n--- Kịch bản 1 (trong grover_builder): {n_search_q1} qubit tìm kiếm, {num_ancillas_oracle1} ancilla Oracle ---")
    print(f"    Oracle sẽ đánh dấu khóa: {target_key1_str}")
    
    oracle_complex_1 = create_complex_mock_oracle(
        n_search_qubits=n_search_q1,
        num_oracle_ancillas=num_ancillas_oracle1,
        mark_state_str=target_key1_str
    )
    print(f"    Oracle phức tạp được tạo với {oracle_complex_1.num_qubits} qubits.")

    iterations1 = int(np.round((np.pi / 4) * np.sqrt(2**n_search_q1)))
    if iterations1 == 0: iterations1 = 1
    print(f"    Số lần lặp Grover: {iterations1}")

    grover_circuit_complex_1 = build_grover_circuit(
        n_qubits=n_search_q1, 
        iterations=iterations1, 
        oracle_circuit=oracle_complex_1
    )
    print("\n--- Mạch Grover (Kịch bản 1 - grover_builder) ---")
    print(f"Tổng số qubit: {grover_circuit_complex_1.num_qubits}")
    print(f"Độ sâu ban đầu: {grover_circuit_complex_1.depth()}")
    # Để xem mạch, bỏ comment (sẽ dài):
    # print(grover_circuit_complex_1.draw(output='text', fold=-1))
    try:
        fig1 = grover_circuit_complex_1.draw(output='mpl', fold=-1)
        fig1.savefig("grover_builder_test_scenario1.png")
        print("Đã lưu sơ đồ mạch Kịch bản 1 vào 'grover_builder_test_scenario1.png'")
    except Exception as e:
        print(f"Không thể vẽ mạch Kịch bản 1 (cần matplotlib): {e}")


    # Kịch bản 2: Sử dụng Oracle phức tạp hơn (ví dụ 3 qubit tìm kiếm, 1 ancilla)
    n_search_q2 = 3
    num_ancillas_oracle2 = 1 # Chỉ 1 ancilla cho result_qubit (mcx(3 control) sẽ tự xử lý)
    target_key2_str = "101"  # MSB-first: q2=1, q1=0, q0=1

    print(f"\n--- Kịch bản 2 (trong grover_builder): {n_search_q2} qubit tìm kiếm, {num_ancillas_oracle2} ancilla Oracle ---")
    print(f"    Oracle sẽ đánh dấu khóa: {target_key2_str}")

    oracle_complex_2 = create_complex_mock_oracle(
        n_search_qubits=n_search_q2,
        num_oracle_ancillas=num_ancillas_oracle2,
        mark_state_str=target_key2_str
    )
    print(f"    Oracle phức tạp được tạo với {oracle_complex_2.num_qubits} qubits.")
    
    iterations2 = int(np.round((np.pi / 4) * np.sqrt(2**n_search_q2)))
    if iterations2 == 0: iterations2 = 1
    print(f"    Số lần lặp Grover: {iterations2}")

    grover_circuit_complex_2 = build_grover_circuit(
        n_qubits=n_search_q2, 
        iterations=iterations2, 
        oracle_circuit=oracle_complex_2
    )
    print("\n--- Mạch Grover (Kịch bản 2 - grover_builder) ---")
    print(f"Tổng số qubit: {grover_circuit_complex_2.num_qubits}")
    print(f"Độ sâu ban đầu: {grover_circuit_complex_2.depth()}")
    try:
        fig2 = grover_circuit_complex_2.draw(output='mpl', fold=-1)
        fig2.savefig("grover_builder_test_scenario2.png")
        print("Đã lưu sơ đồ mạch Kịch bản 2 vào 'grover_builder_test_scenario2.png'")
    except Exception as e:
        print(f"Không thể vẽ mạch Kịch bản 2 (cần matplotlib): {e}")