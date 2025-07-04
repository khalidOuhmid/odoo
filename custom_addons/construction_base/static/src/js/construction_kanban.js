/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";

export class BlgChapterKanbanRenderer extends KanbanRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.chapterStructure = [];
        this.blgIsLoading = false;
        this.blgIsProcessing = false;
        
        onMounted(() => {
            this.loadChapterStructure();
            this.optimizeForManyRecords();
        });
        
        onPatched(() => {
            if (!this.blgIsProcessing && this.chapterStructure.length > 0) {
                this.reorganizeKanbanByChapters();
            }
        });
    }

    async loadChapterStructure() {
        if (this.blgIsLoading) return;
        
        this.blgIsLoading = true;
        this.blgIsProcessing = true;
        
        try {
            const structure = await this.orm.call(
                "construction.chantier", 
                "get_chapter_stage_structure", 
                []
            );
            this.chapterStructure = structure || [];
        } catch (error) {
            console.error("Error loading chapter structure:", error);
            this.chapterStructure = [];
        } finally {
            this.blgIsLoading = false;
            setTimeout(() => {
                this.blgIsProcessing = false;
                this.reorganizeKanbanByChapters();
            }, 100);
        }
    }

    reorganizeKanbanByChapters() {
        if (this.blgIsProcessing) return;
        
        const container = this.el?.querySelector('.o_kanban_renderer');
        if (!container) return;

        // Check if we're in the correct view
        const hasChapterClass = container.classList.contains('o_kanban_with_chapters');
        if (!hasChapterClass) return;

        // Remove any existing chapter container
        const existingChapterContainer = container.querySelector('.blg-chapter-kanban-container');
        if (existingChapterContainer) {
            existingChapterContainer.remove();
        }

        // Hide original kanban groups
        const originalGroups = container.querySelectorAll('.o_kanban_group');
        originalGroups.forEach(group => {
            group.style.display = 'none';
        });

        // Create chapter-based structure
        if (this.chapterStructure.length > 0) {
            const chapterContainer = this.createChapterContainer();
            container.appendChild(chapterContainer);
        }
    }

    createChapterContainer() {
        const chapterContainer = document.createElement('div');
        chapterContainer.className = 'blg-chapter-kanban-container';
        
        this.chapterStructure.forEach(chapter => {
            const chapterSection = this.createChapterSection(chapter);
            chapterContainer.appendChild(chapterSection);
        });

        return chapterContainer;
    }

    createChapterSection(chapter) {
        const section = document.createElement('div');
        section.className = `chapter-section chapter-${chapter.code || '0'}`;
        section.dataset.chapterId = chapter.id;

        // Chapter header
        const header = this.createChapterHeader(chapter);
        section.appendChild(header);

        // Stages container
        const stagesContainer = this.createStagesContainer(chapter);
        section.appendChild(stagesContainer);

        return section;
    }

    createChapterHeader(chapter) {
        const header = document.createElement('div');
        header.className = 'chapter-header';
        
        const headerContent = document.createElement('div');
        headerContent.className = 'chapter-header-content';
        
        const titleSection = document.createElement('div');
        titleSection.className = 'chapter-title-section';
        
        const icon = document.createElement('i');
        icon.className = this.getChapterIcon(chapter.code);
        
        const title = document.createElement('h3');
        title.className = 'chapter-title';
        title.textContent = chapter.name || 'Unknown Chapter';
        
        const badge = document.createElement('span');
        badge.className = 'chapter-badge';
        const totalCount = chapter.total_count || 0;
        badge.textContent = `${totalCount} projet${totalCount !== 1 ? 's' : ''}`;
        
        titleSection.appendChild(icon);
        titleSection.appendChild(title);
        titleSection.appendChild(badge);
        
        const progressBar = this.createChapterProgressBar(chapter);
        
        headerContent.appendChild(titleSection);
        headerContent.appendChild(progressBar);
        header.appendChild(headerContent);
        
        return header;
    }

    createChapterProgressBar(chapter) {
        const progressContainer = document.createElement('div');
        progressContainer.className = 'chapter-progress-container';
        
        const progressBar = document.createElement('div');
        progressBar.className = 'chapter-progress-bar';
        
        let totalProjects = 0;
        let completedStages = 0;
        
        if (chapter.stages && Array.isArray(chapter.stages)) {
            chapter.stages.forEach((stage, index) => {
                totalProjects += stage.count || 0;
                if (index > 0) completedStages += stage.count || 0;
            });
        }
        
        const progressPercentage = totalProjects > 0 ? (completedStages / totalProjects) * 100 : 0;
        
        const progressFill = document.createElement('div');
        progressFill.className = 'chapter-progress-fill';
        progressFill.style.width = `${progressPercentage}%`;
        
        progressBar.appendChild(progressFill);
        progressContainer.appendChild(progressBar);
        
        return progressContainer;
    }

    createStagesContainer(chapter) {
        const container = document.createElement('div');
        container.className = 'stages-container';
        
        if (chapter.stages && Array.isArray(chapter.stages)) {
            chapter.stages.forEach(stage => {
                const stageColumn = this.createStageColumn(stage);
                container.appendChild(stageColumn);
            });
        }
        
        return container;
    }

    createStageColumn(stage) {
        const column = document.createElement('div');
        column.className = 'stage-column';
        column.dataset.stageId = stage.id;
        
        // Find original kanban group and clone its content
        const originalGroup = this.el?.querySelector(`[data-id="${stage.id}"]`);
        if (originalGroup) {
            // Clone the entire group
            const clonedGroup = originalGroup.cloneNode(true);
            clonedGroup.style.display = 'block';
            clonedGroup.classList.add('enhanced-stage-group');
            
            // Enhance the stage header
            this.enhanceStageHeader(clonedGroup, stage);
            
            column.appendChild(clonedGroup);
        } else {
            // Create empty stage column
            const emptyStage = this.createEmptyStageColumn(stage);
            column.appendChild(emptyStage);
        }
        
        return column;
    }

    enhanceStageHeader(groupElement, stage) {
        const header = groupElement.querySelector('.o_kanban_group_header');
        if (header) {
            const title = header.querySelector('.o_column_title');
            if (title) {
                const indicator = document.createElement('span');
                indicator.className = 'stage-indicator';
                const icon = document.createElement('i');
                icon.className = 'fa fa-circle';
                indicator.appendChild(icon);
                
                title.insertBefore(indicator, title.firstChild);
            }
        }
    }

    createEmptyStageColumn(stage) {
        const emptyStage = document.createElement('div');
        emptyStage.className = 'enhanced-stage-group empty-stage';
        
        const header = document.createElement('div');
        header.className = 'enhanced-stage-header';
        
        const title = document.createElement('h4');
        title.textContent = stage.name || 'Unknown Stage';
        
        const indicator = document.createElement('span');
        indicator.className = 'stage-indicator';
        const icon = document.createElement('i');
        icon.className = 'fa fa-circle';
        indicator.appendChild(icon);
        
        header.appendChild(indicator);
        header.appendChild(title);
        
        const body = document.createElement('div');
        body.className = 'empty-stage-body';
        
        const message = document.createElement('p');
        message.className = 'empty-stage-message';
        message.textContent = 'Aucun projet dans cette étape';
        
        body.appendChild(message);
        
        emptyStage.appendChild(header);
        emptyStage.appendChild(body);
        
        return emptyStage;
    }

    getChapterIcon(chapterCode) {
        const iconMap = {
            'PREP': 'fa fa-cogs',
            'EXEC': 'fa fa-hammer',
            'FINI': 'fa fa-check-circle',
            'default': 'fa fa-book'
        };
        
        return iconMap[chapterCode] || iconMap.default;
    }

    optimizeForManyRecords() {
        const kanbanEl = this.el?.querySelector('.blg_modern_kanban');
        if (!kanbanEl) return;

        const cardCount = kanbanEl.querySelectorAll('.blg_card').length;
        const threshold = 20;

        if (cardCount > threshold) {
            kanbanEl.classList.add('compact-mode');
        } else {
            kanbanEl.classList.remove('compact-mode');
        }

        // Add tooltips
        this._addTooltips(kanbanEl);
        
        // Enhance drag & drop
        this._enhanceDragDrop(kanbanEl);
        
        // Initialize basic animations
        this._initBasicAnimations(kanbanEl);
    }

    _addTooltips(kanbanEl) {
        // Tooltips pour les statuts
        kanbanEl.querySelectorAll('.status-dot').forEach(dot => {
            const card = dot.closest('.blg_card');
            if (card) {
                const statusText = this._getStatusText(card);
                dot.setAttribute('title', statusText);
            }
        });

        // Tooltips pour les métriques
        kanbanEl.querySelectorAll('.metric').forEach(metric => {
            const icon = metric.querySelector('i');
            if (icon) {
                const tooltipText = this._getMetricTooltip(icon);
                metric.setAttribute('title', tooltipText);
            }
        });
    }

    _enhanceDragDrop(kanbanEl) {
        kanbanEl.querySelectorAll('.blg_card').forEach(card => {
            card.addEventListener('dragstart', () => {
                card.classList.add('dragging');
            });

            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
            });
        });

        // Améliorer les zones de drop
        kanbanEl.querySelectorAll('.o_kanban_group').forEach(group => {
            group.addEventListener('dragover', (e) => {
                e.preventDefault();
                group.classList.add('drag-over');
            });

            group.addEventListener('dragleave', () => {
                group.classList.remove('drag-over');
            });

            group.addEventListener('drop', () => {
                group.classList.remove('drag-over');
            });
        });
    }

    _initBasicAnimations(kanbanEl) {
        // Animation d'apparition simple pour les nouvelles cartes
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated-in');
                }
            });
        }, { threshold: 0.1 });

        kanbanEl.querySelectorAll('.blg_card:not(.animated-in)').forEach(card => {
            observer.observe(card);
        });
    }

    _getStatusText(card) {
        if (card.classList.contains('urgent')) return 'Critique - En retard';
        if (card.classList.contains('warning')) return 'Attention - Échéance proche';
        if (card.classList.contains('completed')) return 'Terminé';
        return 'En cours';
    }

    _getMetricTooltip(icon) {
        if (icon.classList.contains('fa-euro')) return 'Budget total du projet';
        if (icon.classList.contains('fa-clock-o')) return 'Jours restants avant échéance';
        if (icon.classList.contains('fa-users')) return 'Équipe assignée';
        if (icon.classList.contains('fa-cog')) return 'État du projet';
        return 'Métrique du projet';
    }
}

export class BlgChapterKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    onGroupDragStart(ev) {
        // Désactiver le drag and drop des groupes
        ev.preventDefault();
        return false;
    }

    onGroupDrop(ev) {
        // Désactiver le drop des groupes
        ev.preventDefault();
        return false;
    }
}

// Enregistrer les nouveaux composants
registry.category("views").add("blg_chapter_kanban", {
    ...kanbanView,
    Controller: BlgChapterKanbanController,
    Renderer: BlgChapterKanbanRenderer,
});

// CSS animations supplémentaires
const constructionStyles = document.createElement('style');
constructionStyles.textContent = `
    /* Animations de base pour le kanban construction */
    .blg_card:not(.animated-in) {
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s ease;
    }

    .blg_card.animated-in {
        opacity: 1;
        transform: translateY(0);
    }

    .blg_card.dragging {
        opacity: 0.8;
        transform: rotate(2deg) scale(1.02);
        transition: all 0.2s ease;
    }

    .o_kanban_group.drag-over {
        background-color: rgba(0, 123, 255, 0.05);
        border-color: #007bff;
        transition: all 0.2s ease;
    }

    /* Améliorations responsives */
    @media (max-width: 768px) {
        .blg_modern_kanban .o_kanban_group {
            min-width: 260px;
            margin: 8px 2px;
        }
        
        .blg_modern_kanban {
            padding: 8px 4px;
        }
    }

    /* Mode performance pour beaucoup de cartes */
    .blg_modern_kanban.performance-mode .blg_card {
        transition: none;
    }

    .blg_modern_kanban.performance-mode .blg_card:hover {
        transition: transform 0.2s ease;
    }
`;

// Ajouter les styles au document
if (!document.getElementById('construction-kanban-styles')) {
    constructionStyles.id = 'construction-kanban-styles';
    document.head.appendChild(constructionStyles);
} 