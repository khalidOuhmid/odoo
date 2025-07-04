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
                "blg.chantier", 
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
            clonedGroup.className += ' enhanced-stage-group';
            
            // Enhance the header
            this.enhanceStageHeader(clonedGroup, stage);
            
            column.appendChild(clonedGroup);
        } else {
            // Create empty stage column
            const emptyColumn = this.createEmptyStageColumn(stage);
            column.appendChild(emptyColumn);
        }
        
        return column;
    }

    enhanceStageHeader(groupElement, stage) {
        const header = groupElement.querySelector('.o_kanban_group_header');
        if (header) {
            header.className += ' enhanced-stage-header';
            
            // Add stage indicator
            const indicator = document.createElement('div');
            indicator.className = 'stage-indicator';
            indicator.innerHTML = `<i class="fa fa-circle"></i>`;
            
            const titleElement = header.querySelector('.o_column_title');
            if (titleElement) {
                titleElement.insertBefore(indicator, titleElement.firstChild);
            }
        }
    }

    createEmptyStageColumn(stage) {
        const emptyGroup = document.createElement('div');
        emptyGroup.className = 'o_kanban_group enhanced-stage-group empty-stage';
        
        const header = document.createElement('div');
        header.className = 'o_kanban_group_header enhanced-stage-header';
        
        const title = document.createElement('div');
        title.className = 'o_kanban_group_title';
        
        const indicator = document.createElement('div');
        indicator.className = 'stage-indicator';
        indicator.innerHTML = `<i class="fa fa-circle"></i>`;
        
        const titleText = document.createElement('strong');
        titleText.className = 'o_column_title';
        titleText.textContent = stage.name || 'Unknown Stage';
        
        const counter = document.createElement('span');
        counter.className = 'o_kanban_counter';
        counter.textContent = '0 projet';
        
        title.appendChild(indicator);
        title.appendChild(titleText);
        title.appendChild(counter);
        header.appendChild(title);
        
        const body = document.createElement('div');
        body.className = 'empty-stage-body';
        body.innerHTML = '<div class="empty-stage-message">Aucun projet dans cette étape</div>';
        
        emptyGroup.appendChild(header);
        emptyGroup.appendChild(body);
        
        return emptyGroup;
    }

    getChapterIcon(chapterCode) {
        const icons = {
            '1': 'fa fa-file-text-o',
            '2': 'fa fa-cogs',
            '3': 'fa fa-hammer',
            '4': 'fa fa-check-circle',
            '5': 'fa fa-shield',
            '6': 'fa fa-archive'
        };
        return icons[chapterCode] || 'fa fa-folder';
    }

    optimizeForManyRecords() {
        // Activer le mode compact si beaucoup de cartes
        const container = this.el?.querySelector('.blg_modern_kanban');
        if (!container) return;

        const cards = container.querySelectorAll('.blg_card');
        const groups = container.querySelectorAll('.o_kanban_group');
        
        // Si plus de 50 cartes au total ou plus de 15 cartes dans une colonne
        let totalCards = cards.length;
        let maxCardsInGroup = 0;
        
        groups.forEach(group => {
            const groupCards = group.querySelectorAll('.blg_card');
            if (groupCards.length > maxCardsInGroup) {
                maxCardsInGroup = groupCards.length;
            }
        });

        if (totalCards > 50 || maxCardsInGroup > 15) {
            container.classList.add('compact-mode');
        }

        // Optimisation du scroll pour les groupes avec beaucoup de cartes
        groups.forEach(group => {
            const groupCards = group.querySelectorAll('.blg_card');
            if (groupCards.length > 20) {
                group.style.maxHeight = '70vh';
                group.style.overflowY = 'auto';
                group.style.scrollBehavior = 'smooth';
            }
        });
    }
}

export class BlgChapterKanbanController extends KanbanController {
    setup() {
        super.setup();
    }

    /**
     * Désactiver complètement le drag and drop des groupes
     */
    onGroupDragStart(ev) {
        ev.preventDefault();
        return false;
    }
    
    /**
     * Désactiver le drop sur les groupes
     */
    onGroupDrop(ev) {
        ev.preventDefault();
        return false;
    }
}

export const blgChapterKanbanView = {
    ...kanbanView,
    Renderer: BlgChapterKanbanRenderer,
    Controller: BlgChapterKanbanController,
};

// Register the view with the correct name
registry.category("views").add("blg_chapter_kanban", blgChapterKanbanView);
