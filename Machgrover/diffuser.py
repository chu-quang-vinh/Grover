# diffuser.py

from qiskit import QuantumCircuit, QuantumRegister
import csv # Để làm việc với file CSV

def build_diffuser(n_qubits: int) -> QuantumCircuit:
    """
    Xây dựng mạch diffuser (bộ khuếch tán) cho thuật toán Grover.

    Mạch diffuser thực hiện phép phản xạ quanh trạng thái chồng chập đồng đều |s>.
    Nó bao gồm các bước: H^n . X^n . (Multi-Controlled Z) . X^n . H^n
    Trong đó Multi-Controlled Z (MCZ_0) đảo pha trạng thái |0...0>,
    hoặc tương đương, MCZ_all_1 đảo pha trạng thái |1...1> nếu X^n đã được áp dụng.

    Args:
        n_qubits: Số lượng qubit cho diffuser.

    Returns:
        QuantumCircuit: Mạch lượng tử của diffuser.
    """
    if not isinstance(n_qubits, int) or n_qubits < 1:
        raise ValueError("Số lượng qubit (n_qubits) phải là một số nguyên dương.")

    qc = QuantumCircuit(n_qubits, name=f"Diffuser_{n_qubits}q")

    # 1. Áp dụng cổng Hadamard (H) cho tất cả các qubit
    # (Đây là bước đầu của D = H^n . (2|0><0| - I) . H^n,
    # hoặc là bước tạo uniform superposition ban đầu nếu diffuser được định nghĩa là
    # H^n . X^n . MCZ_all_1 . X^n . H^n để phản xạ quanh |s>)
    # Theo yêu cầu "tạo uniform superposition rồi reflect quanh trung bình",
    # superposition này là một phần của diffuser.
    for qubit_idx in range(n_qubits):
        qc.h(qubit_idx)

    # 2. Áp dụng cổng Pauli-X (NOT) cho tất cả các qubit
    for qubit_idx in range(n_qubits):
        qc.x(qubit_idx)
    qc.barrier()

    # 3. Áp dụng cổng Multi-Controlled Z (MCZ_all_1 - đảo pha trạng thái |1...1>)
    # Được triển khai bằng H . MCX . H trên qubit mục tiêu.
    if n_qubits == 1:
        # Với 1 qubit, (H.X).Z.(X.H) = H.Z.H
        # Hoặc nếu diffuser là H.Z.H, thì sau H ban đầu, chỉ cần Z.
        # Theo cấu trúc H^n . X^n . MCZ_all_1 . X^n . H^n:
        # H . X . (Z) . X . H
        qc.z(0)
    elif n_qubits > 1:
        # Chọn qubit cuối cùng làm qubit mục tiêu cho MCX
        target_qubit_mcx = n_qubits - 1
        # Các qubit còn lại là qubit điều khiển
        control_qubits_mcx = list(range(n_qubits - 1))
        
        qc.h(target_qubit_mcx)
        qc.mcx(control_qubits_mcx, target_qubit_mcx) # Qiskit mcx tự xử lý phân rã
        qc.h(target_qubit_mcx)
    qc.barrier()

    # 4. Áp dụng cổng Pauli-X (NOT) cho tất cả các qubit (hoàn tác bước 2)
    for qubit_idx in range(n_qubits):
        qc.x(qubit_idx)

    # 5. Áp dụng cổng Hadamard (H) cho tất cả các qubit (hoàn tác bước 1)
    for qubit_idx in range(n_qubits):
        qc.h(qubit_idx)
        
    return qc

# --- Phần Benchmark Diffuser ---
if __name__ == "__main__":
    n_qubit_values_for_benchmark = [4, 6, 8, 10]
    benchmark_results = []

    print("--- Benchmarking Diffuser ---")
    for n_q in n_qubit_values_for_benchmark:
        print(f"Xây dựng và đánh giá diffuser cho n_qubits = {n_q}...")
        try:
            diffuser_circuit = build_diffuser(n_q)
            depth = diffuser_circuit.depth()
            num_qubits_in_circuit = diffuser_circuit.num_qubits # Sẽ bằng n_q

            # In kết quả ra console
            print(f"  n_qubits = {n_q}")
            print(f"  Số qubit trong mạch: {num_qubits_in_circuit}")
            print(f"  Độ sâu mạch: {depth}")
            print(diffuser_circuit.draw(output='text', fold=-1)) # Bỏ comment nếu muốn xem mạch

            benchmark_results.append({
                'n_qubits': n_q,
                'depth': depth,
                'num_qubits_reported': num_qubits_in_circuit
            })
        except Exception as e:
            print(f"Lỗi khi benchmark diffuser cho n_qubits = {n_q}: {e}")
    
    # Lưu kết quả benchmark vào file CSV
    csv_file_name = 'diffuser_benchmarks.csv'
    csv_headers = ['n_qubits', 'depth', 'num_qubits_reported']

    try:
        with open(csv_file_name, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            writer.writerows(benchmark_results)
        print(f"\nĐã lưu kết quả benchmark vào file: {csv_file_name}")
    except IOError:
        print(f"Lỗi: Không thể ghi vào file {csv_file_name}")

    print("\n--- Hoàn thành Benchmark Diffuser ---")