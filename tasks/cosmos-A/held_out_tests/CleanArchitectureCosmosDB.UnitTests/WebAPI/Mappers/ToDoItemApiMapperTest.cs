using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.WebAPI.Mappers;
using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using Newtonsoft.Json;
using System;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.WebAPI.Mappers
{
    public class ToDoItemApiMapperTest
    {
        [Fact]
        public void ToModel_MapsAllProperties()
        {
            var entity = new ToDoItem
            {
                Id = "cat:123",
                Category = "cat",
                Title = "Test Title"
            };

            var model = ToDoItemApiMapper.ToModel(entity);

            Assert.Equal("cat:123", model.Id);
            Assert.Equal("cat", model.Category);
            Assert.Equal("Test Title", model.Title);
            Assert.False(model.IsCompleted);
        }

        [Fact]
        public void ToModel_MapsIsCompletedTrue()
        {
            var entity = new ToDoItem
            {
                Id = "cat:456",
                Category = "cat",
                Title = "Completed Item"
            };
            entity.MarkComplete();

            var model = ToDoItemApiMapper.ToModel(entity);

            Assert.True(model.IsCompleted);
        }

        [Fact]
        public void ToEntity_MapsFromCreateCommand()
        {
            var command = new Create.CreateToDoItemCommand
            {
                Category = "work",
                Title = "New Task"
            };

            var entity = ToDoItemApiMapper.ToEntity(command);

            Assert.Equal("work", entity.Category);
            Assert.Equal("New Task", entity.Title);
            Assert.False(entity.IsCompleted);
        }

        [Fact]
        public void ToAuditModel_MapsCorrectly()
        {
            var todoItem = new ToDoItem
            {
                Id = "cat:789",
                Category = "cat",
                Title = "Audited Item"
            };
            var serialized = JsonConvert.SerializeObject(todoItem);

            var audit = new Audit("ToDoItem", "cat:789", serialized)
            {
                Id = "cat:789:guid-1"
            };

            var auditModel = ToDoItemApiMapper.ToAuditModel(audit);

            Assert.NotNull(auditModel.ToDoItemModel);
            Assert.Equal("cat:789", auditModel.ToDoItemModel.Id);
            Assert.Equal("cat", auditModel.ToDoItemModel.Category);
            Assert.Equal("Audited Item", auditModel.ToDoItemModel.Title);
        }

        [Fact]
        public void ToAuditModel_MapsDateCreatedUTC()
        {
            var audit = new Audit("ToDoItem", "cat:001", "{}")
            {
                Id = "cat:001:guid-2"
            };
            var expectedDate = audit.DateCreatedUTC;

            var auditModel = ToDoItemApiMapper.ToAuditModel(audit);

            Assert.Equal(expectedDate, auditModel.DateCreatedUTC);
        }
    }
}
