// Arquivo: static/js/file-selection.js

document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('csvFiles');
    const fileList = document.getElementById('fileList');
    const clearButton = document.getElementById('clearButton');
    const recursiveCheck = document.getElementById('recursiveCheck');
    const duplicateWarning = document.getElementById('duplicateWarning');
    const analyzeButton = document.getElementById('analyzeButton');

    // Array para armazenar arquivos
    let selectedFiles = [];
    let fileHashes = new Map(); // Para verificar duplicatas

    // Função para calcular um hash simples para verificar duplicatas
    function calculateFileHash(file) {
        return `${file.name}_${file.size}_${file.lastModified}`;
    }

    // Função para adicionar arquivos à lista
    function addFilesToList(files, pathPrefix = '') {
        const recursive = recursiveCheck.checked;
        
        Array.from(files).forEach(file => {
            // Verificar se é CSV
            if (file.name.toLowerCase().endsWith('.csv')) {
                const fileHash = calculateFileHash(file);
                
                // Verificar duplicatas
                if (!fileHashes.has(fileHash)) {
                    fileHashes.set(fileHash, true);
                    
                    // Adicionar à lista de arquivos
                    const filePath = pathPrefix ? `${pathPrefix}/${file.name}` : file.name;
                    selectedFiles.push({
                        file: file,
                        path: filePath
                    });
                    
                    // Atualizar interface
                    const fileItem = document.createElement('div');
                    fileItem.className = 'list-group-item d-flex justify-content-between align-items-center';
                    fileItem.innerHTML = `
                        <div>
                            <i class="bi bi-file-earmark-text text-primary me-2"></i>
                            <span class="file-path" title="${filePath}">${filePath}</span>
                        </div>
                        <button type="button" class="btn btn-sm btn-outline-danger remove-file" data-hash="${fileHash}">
                            <i class="bi bi-trash"></i>
                        </button>
                    `;
                    fileList.appendChild(fileItem);
                    
                    // Adicionar evento para remover arquivo
                    fileItem.querySelector('.remove-file').addEventListener('click', function() {
                        const hash = this.getAttribute('data-hash');
                        removeFile(hash);
                        fileItem.remove();
                    });
                } else {
                    // Exibir aviso de duplicata
                    duplicateWarning.style.display = 'block';
                }
            }
            
            // Verificar se é diretório e recursão está habilitada
            if (file.isDirectory && recursive) {
                const directoryReader = file.createReader();
                directoryReader.readEntries(function(entries) {
                    addFilesToList(entries, file.name);
                });
            }
        });
        
        // Atualizar visibilidade da lista
        if (selectedFiles.length > 0) {
            fileList.style.display = 'block';
            updateFileCount();
        } else {
            fileList.style.display = 'none';
        }
    }
    
    // Função para remover arquivo pelo hash
    function removeFile(hash) {
        fileHashes.delete(hash);
        selectedFiles = selectedFiles.filter(item => calculateFileHash(item.file) !== hash);
        updateFileCount();
        
        if (selectedFiles.length === 0) {
            fileList.style.display = 'none';
        }
    }
    
    // Atualizar contador de arquivos
    function updateFileCount() {
        analyzeButton.textContent = `Analisar Arquivos (${selectedFiles.length})`;
    }
    
    // Eventos de Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropZone.classList.add('drop-zone-active');
    }
    
    function unhighlight() {
        dropZone.classList.remove('drop-zone-active');
    }
    
    // Evento quando arquivos são arrastados para a zona
    dropZone.addEventListener('drop', function(e) {
        const items = e.dataTransfer.items;
        if (items) {
            // DataTransferItemList suporta diretórios
            for (let i = 0; i < items.length; i++) {
                const item = items[i].webkitGetAsEntry();
                if (item) {
                    scanEntry(item, '');
                }
            }
        } else {
            // Fallback para browsers que não suportam WebkitGetAsEntry
            const files = e.dataTransfer.files;
            addFilesToList(files);
        }
    });
    
    // Função recursiva para escanear entradas (arquivos e diretórios)
    function scanEntry(entry, path) {
        if (entry.isFile) {
            entry.file(file => {
                if (file.name.toLowerCase().endsWith('.csv')) {
                    const fullPath = path ? `${path}/${file.name}` : file.name;
                    
                    // Atualizar informações do arquivo para incluir o caminho
                    file.customPath = fullPath;
                    addFilesToList([file]);
                }
            });
        } else if (entry.isDirectory && recursiveCheck.checked) {
            const dirPath = path ? `${path}/${entry.name}` : entry.name;
            const reader = entry.createReader();
            
            reader.readEntries(entries => {
                entries.forEach(e => {
                    scanEntry(e, dirPath);
                });
            });
        }
    }
    
    // Evento quando arquivos são selecionados pelo input
    fileInput.addEventListener('change', function() {
        // Se o atributo 'webkitdirectory' estiver presente
        if (this.files) {
            addFilesToList(this.files);
        }
    });
    
    // Clique na zona para selecionar arquivos/pastas
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });
    
    // Limpar seleção de arquivos
    clearButton.addEventListener('click', function() {
        selectedFiles = [];
        fileHashes.clear();
        fileList.innerHTML = '';
        fileList.style.display = 'none';
        fileInput.value = '';
        duplicateWarning.style.display = 'none';
        analyzeButton.textContent = 'Analisar Arquivos';
    });
    
    // Preparar o formulário para envio
    document.getElementById('fileUploadForm').addEventListener('submit', function(e) {
        if (selectedFiles.length === 0) {
            e.preventDefault();
            alert('Por favor, selecione pelo menos um arquivo para análise.');
            return false;
        }
        
        // Criar FormData manualmente para incluir os arquivos selecionados
        e.preventDefault();
        const formData = new FormData(this);
        
        // Remover arquivos existentes e adicionar apenas os da nossa lista
        formData.delete('csvFiles');
        selectedFiles.forEach(fileObj => {
            formData.append('csvFiles', fileObj.file, fileObj.path);
        });
        
        // Enviar via fetch API
        const submitButton = document.getElementById('analyzeButton');
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Analisando...';
        
        fetch('/', {
            method: 'POST',
            body: formData
        })
        .then(response => response.text())
        .then(html => {
            document.open();
            document.write(html);
            document.close();
        })
        .catch(error => {
            console.error('Erro:', error);
            submitButton.disabled = false;
            submitButton.textContent = 'Analisar Arquivos';
            alert('Ocorreu um erro ao enviar os arquivos. Por favor, tente novamente.');
        });
    });
});